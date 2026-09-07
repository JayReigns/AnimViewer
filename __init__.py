bl_info = {
    "name": "Anim Viewer",
    "author": "JayReigns",
    "version": (1, 1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Animation Tab",
    "description": "View and Assign all Actions",
    "category": "Animation"
}

import bpy
from mathutils import Vector
from bpy.props import IntProperty, EnumProperty, BoolProperty, PointerProperty
from bpy.types import Operator, UIList, Panel, PropertyGroup

LOCATION_CONSTRAINT_NAME = "AnimV Inplace Constraint"

def get_global_props():
    return bpy.context.window_manager.animv_props

# cache selected object incase hidden after selection
_cached_obj = None
def get_active_obj():
    global _cached_obj

    pinned = get_global_props().pin_object

    # if pinned retuen the previous object if not None
    if pinned and _cached_obj:
        return _cached_obj
    
    _cached_obj = bpy.context.active_object
    return _cached_obj


#########################################################################################
# MOTION ANALYSIS FOR INLACE AXES DETECTION
#########################################################################################


def get_max_displacement_vector(action, data_path, start_frame, end_frame):
    fcurves = {
        fcurve.array_index: fcurve
        for fcurve in action.fcurves
        if fcurve.data_path == data_path and fcurve.array_index < 3
    }
    sample_count = min(max(2, int(end_frame - start_frame) + 1), 120)
    frames = [
        start_frame + (end_frame - start_frame) * index / (sample_count - 1)
        for index in range(sample_count)
    ]
    start_location = Vector((
        fcurves[axis].evaluate(start_frame) if axis in fcurves else 0.0
        for axis in range(3)
    ))
    max_displacement = Vector((0.0, 0.0, 0.0))
    max_distance_squared = 0.0

    for frame in frames[1:]:
        location = Vector((
            fcurves[axis].evaluate(frame) if axis in fcurves else 0.0
            for axis in range(3)
        ))
        displacement = location - start_location
        distance_squared = displacement.length_squared
        if distance_squared > max_distance_squared:
            max_distance_squared = distance_squared
            max_displacement = displacement

    return max_displacement


def detect_inplace_axes(ob, action):
    start_frame, end_frame = action.frame_range
    world_rotation = ob.matrix_world.to_3x3()
    world_axis_scores = [0.0, 0.0, 0.0]

    if ob.type == 'ARMATURE':
        roots = [bone for bone in ob.data.bones if bone.parent is None]
        for bone in roots:
            data_path = f'pose.bones["{bone.name}"].location'
            displacement = get_max_displacement_vector(
                action, data_path, start_frame, end_frame
            )
            world_displacement = (
                world_rotation @ bone.matrix_local.to_3x3() @ displacement
            )
            for axis in range(3):
                world_axis_scores[axis] += world_displacement[axis] ** 2
    else:
        displacement = get_max_displacement_vector(
            action, 'location', start_frame, end_frame
        )
        world_displacement = world_rotation @ displacement
        for axis in range(3):
            world_axis_scores[axis] += world_displacement[axis] ** 2

    if max(world_axis_scores) < 0.0001:
        return (False, False, False)

    axis = max(range(3), key=world_axis_scores.__getitem__)
    result = [False, False, False]
    result[axis] = True
    return tuple(result)


def get_inplace_axes(ob, props):
    if props.inplace_axes == 'AUTO':
        if ob.animation_data and ob.animation_data.action:
            return detect_inplace_axes(ob, ob.animation_data.action)
        return (False, False, False)

    return tuple(axis in props.inplace_axes for axis in 'XYZ')


#########################################################################################
# PROPERTY UPDATES
#########################################################################################


def update_speed(self, context):
    props = get_global_props()
    scn = bpy.context.scene
    rnd = scn.render
    speed = float(props.speed)
    
    frame_duration = 100

    ob = get_active_obj()
    if ob and ob.animation_data and ob.animation_data.action:
        action = ob.animation_data.action
        frame_start = action.frame_range[0]
        frame_end = action.frame_range[1]

        frame_duration = frame_end - frame_start + 1

        scn.frame_preview_start = int(frame_start / speed)
        scn.frame_preview_end = int(frame_end / speed)
        scn.use_preview_range = True
    
    rnd.frame_map_old = int(frame_duration)
    rnd.frame_map_new = int(frame_duration / speed)


def update_constraints(self, context):
    ob = get_active_obj()
    if not ob:
        return

    targets = get_constraint_targets(ob)

    axes = get_inplace_axes(ob, self)

    for target in targets:
        lim_loc_constr = target.constraints.get(LOCATION_CONSTRAINT_NAME)

        if any(axes):
            if not lim_loc_constr:
                lim_loc_constr = target.constraints.new('LIMIT_LOCATION')
                lim_loc_constr.name = LOCATION_CONSTRAINT_NAME

            lim_loc_constr.use_min_x = axes[0]
            lim_loc_constr.use_max_x = axes[0]
            lim_loc_constr.min_x = 0.0
            lim_loc_constr.max_x = 0.0
            lim_loc_constr.use_min_y = axes[1]
            lim_loc_constr.use_max_y = axes[1]
            lim_loc_constr.min_y = 0.0
            lim_loc_constr.max_y = 0.0
            lim_loc_constr.use_min_z = axes[2]
            lim_loc_constr.use_max_z = axes[2]
            lim_loc_constr.min_z = 0.0
            lim_loc_constr.max_z = 0.0
            lim_loc_constr.owner_space = 'WORLD'
            lim_loc_constr.influence = 1.0

        elif lim_loc_constr:
            target.constraints.remove(lim_loc_constr)


def get_constraint_targets(ob):
    if ob.type == 'ARMATURE':
        return [
            ob.pose.bones[bone.name]
            for bone in ob.data.bones
            if bone.parent is None
        ]

    return [ob]


def remove_inplace_constraints(ob):
    for target in get_constraint_targets(ob):
        constraint = target.constraints.get(LOCATION_CONSTRAINT_NAME)
        if constraint:
            target.constraints.remove(constraint)


def update_animation(self, context):

    props = get_global_props()

    ob = get_active_obj()
    if not ob:
        return
    
    if ob.animation_data == None:
        ob.animation_data_create()
    
    def reset_pose(o):
        o.location = (0, 0, 0)
        o.rotation_quaternion = (1, 0, 0, 0)
        o.rotation_axis_angle = (0, 0, 1, 0)
        o.rotation_euler = (0, 0, 0)
        o.scale = (1, 1, 1)

    # reset pose
    if ob.pose: # for armatures
        for n in ob.pose.bones:
            reset_pose(n)
    else:
        reset_pose(ob)
    
    action = bpy.data.actions[self.anim_list_index]
    ob.animation_data.action = action

    if bpy.app.version >= (4, 4, 0):
        ob.animation_data.action_slot = action.slots[0]

    update_speed(self, context)
    update_constraints(ob.animv_props, context)
        
    # reset frame to start
    scn = bpy.context.scene
    scn.frame_current = scn.frame_preview_start
    

#########################################################################################
# OPERATORS
#########################################################################################

class ANIMV_OT_UnlinkAction(Operator):
    """Sets animation speed"""
    bl_idname = "animv.unlink_action"
    bl_label = "Remove Action"
    bl_description = "Unlink the action from the object"
        
    @classmethod
    def poll(cls, context):
        ob = get_active_obj()
        return ob is not None \
            and ob.animation_data is not None \
            and ob.animation_data.action is not None \
    
    def execute(self, context):
        ob = get_active_obj()
        ob.animation_data.action = None

        # reset settings
        scn = bpy.context.scene
        rnd = scn.render

        scn.use_preview_range = False

        # reset frame mapping
        rnd.frame_map_old = 100
        rnd.frame_map_new = 100

        remove_inplace_constraints(ob)
        
        return{'FINISHED'}


#########################################################################################
# PANELS
#########################################################################################


def update_anim_list_index():
    ob = get_active_obj()
    
    if ob and ob.animation_data and ob.animation_data.action:
        ui_action_name = bpy.data.actions[ob.animv_props.anim_list_index].name
        data_action_name = ob.animation_data.action.name
        if ui_action_name != data_action_name:
            bpy.app.timers.register(my_timer_function, first_interval=0)
    
    # no need to update if ob is None or has no action
    # since UIList active_index cant be None or -1 to make nothing selected


def my_timer_function():
    ob = get_active_obj()
    if ob and ob.animation_data and ob.animation_data.action:
        idx = bpy.data.actions.find(ob.animation_data.action.name)
        ob.animv_props.anim_list_index = idx
    # no need to update if ob is None or has no action
    # return None # Returning None will keep the timer active


class ANIMV_UL_Action_List(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        self.use_filter_show = True
        
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon_value=icon)

            ob = get_active_obj()
            action = item
            # draw cancel button if the action is linked to the object
            if ob.animation_data and ob.animation_data.action == action:
                layout.operator("animv.unlink_action", text="", icon='CANCEL', emboss=False)
            
        elif self.layout_type in {'GRID'}:
            pass
        global filter_name2
        filter_name2 = self.filter_name


class ANIMV_PT_Viewer(Panel):
    bl_label = "Animation Viewer"
    bl_idname = "ANIMV_PT_Viewer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Animation"

    def draw(self, context):
        layout = self.layout
        props = get_global_props()
        
        ob = get_active_obj()
        if not ob:
            layout.label(text= "Select an Object/Armature", icon="POSE_HLT")
            return
        
        # hack to detect blender data changes in ui context
        # and update using app.timer
        update_anim_list_index()

        row = layout.row(align=True)
        row.label(text= ob.name, icon="POSE_HLT")
        row.prop(props, 'pin_object', text="", icon='PINNED' if props.pin_object else 'UNPINNED')
        row.prop(bpy.context.scene, "use_preview_range", icon_only=True)

        row = layout.row(align=True)
        row.prop(ob.animv_props, "inplace_axes", text="Inplace")

        row = layout.row(align=True)
        row.label(text="Speed:")
        row.prop(props, 'speed', expand=True)

        layout.template_list("ANIMV_UL_Action_List", "", bpy.data, "actions", ob.animv_props, "anim_list_index")


#########################################################################################
# PROPERTIES
#########################################################################################


class ANIMV_Object_Props(PropertyGroup):
    anim_list_index: IntProperty(
        update=update_animation,
        description="Anim Viewer's highlighted action on list for this object"
    )
    inplace_axes: EnumProperty(
        name="Inplace",
        description="Limit translations in these axes (Uses Constraints)",
        update=update_constraints,
        items=[
            ('NONE', 'None', 'Do not limit translation'),
            ('AUTO', 'Auto', 'Detect primary translation axes from the active action'),
            ('X', 'X', 'Limit X translation'),
            ('Y', 'Y', 'Limit Y translation'),
            ('Z', 'Z', 'Limit Z translation'),
            ('XY', 'XY', 'Limit X and Y translation'),
            ('XZ', 'XZ', 'Limit X and Z translation'),
            ('YZ', 'YZ', 'Limit Y and Z translation'),
            ('XYZ', 'XYZ', 'Limit X, Y, and Z translation'),
        ],
        default='NONE',
    )


class ANIMV_Props(PropertyGroup):
    pin_object: BoolProperty(
        name="pin_object",
        description="Pin current object regardless of selection",
        # DONT UPDATE: updating causes to apply animation, when unpinned on different object
        #update = update_animation,
        default=False,
    )
    speed : bpy.props.EnumProperty(
        name='speed', 
        description='Animation playback speed',
        update = update_speed,
        items=[
            ('0.25', '0.25', ''), 
            ('0.5', '0.5', ''), 
            ('1', '1', ''),
            ('1.25', '1.25', ''),
            ('1.5', '1.5', ''),
            ('2', '2', ''),
        ],
        default="1",
    )


#########################################################################################
# REGISTER/UNREGISTER
#########################################################################################


classes = (
    ANIMV_OT_UnlinkAction,
    ANIMV_UL_Action_List,
    ANIMV_PT_Viewer,
    ANIMV_Object_Props,
    ANIMV_Props,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Object.animv_props = PointerProperty(
        type=ANIMV_Object_Props,
        name="ANIMV Object Props",
    )
    bpy.types.WindowManager.animv_props = PointerProperty(
        type=ANIMV_Props,
        name="ANIMV Props",
    )


def unregister():

    del bpy.types.Object.animv_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()