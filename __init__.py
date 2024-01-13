bl_info = {
    "name": "Anim Viewer",
    "author": "JayReigns",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Animation Tab",
    "description": "View and Assign all Actions",
    "category": "Animation"
}

import bpy
from bpy.props import IntProperty, FloatProperty, EnumProperty, StringProperty, BoolProperty, PointerProperty
from bpy.types import Operator, Menu, UIList, Panel, PropertyGroup, AddonPreferences


def get_global_props():
    return bpy.context.window_manager.animv_props

# cache selected object incase hidden after selection
def get_active_obj():
    if bpy.context.active_object:
        get_active_obj.obj = bpy.context.active_object
    
    try:
        return get_active_obj.obj
    except:
        return None


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
    
    action = bpy.data.actions[ob.anim_list_index]
    ob.animation_data.action = action

    speed = props.speed
        
    scn = bpy.context.scene
    rnd = scn.render
    
    scn.use_preview_range = True
    scn.frame_preview_start = int(action.frame_range[0] / speed)
    scn.frame_preview_end = int(action.frame_range[1] / speed)

    scn.frame_current = scn.frame_preview_start
    
    # frame_map_old and frame_map_new are in range [1, 900]
    length = min(900, action.frame_range[1] - action.frame_range[0] + 1)
    rnd.frame_map_old = int(length)
    rnd.frame_map_new = int(length / speed)

    def make_inplace(action, data_path, mute=True):
        x = action.fcurves.find(data_path, index=0)
        y = action.fcurves.find(data_path, index=1)
        z = action.fcurves.find(data_path, index=2)
        if x: x.mute = mute
        if y: y.mute = mute
        if z: z.mute = mute

    # check if we modified previous action
    if props.action_changed_inplace:
        prev_action = bpy.data.actions[props.action_changed_inplace]
        data_path = props.data_path_changed_inplace
        make_inplace(prev_action, data_path, mute=False)

    # inplace
    if props.inplace:
        if ob.pose: # for armatures
            # blender maintains hierarchy order, so 0th bone is the root bone
            # 0th bone also can be a stray bone and the root bone is next
            root_name = ob.pose.bones[0].name

            # find location xyz fcurves
            data_path = f'pose.bones["{root_name}"].location'
        else:
            data_path = 'location'
        
        make_inplace(action, data_path)
        # used to revert changes
        # TODO: add further check to detect which channels are changed
        props.action_changed_inplace = action.name
        props.data_path_changed_inplace = data_path


#########################################################################################
# OPERATORS
#########################################################################################


class ANIMV_OT_SetSpeed(Operator):
    """Sets animation speed"""
    bl_idname = "animv.set_speed"
    bl_label = "Set Animation Speed"
    
    speed : FloatProperty(name="Animation Speed", default=1.0)
    
    @classmethod
    def poll(cls, context):
        ob = get_active_obj()
        return ob is not None \
            and ob.animation_data is not None \
            and ob.animation_data.action is not None \
    
    def execute(self, context):
        
        props = get_global_props()
        props.speed = self.speed
        
        return{'FINISHED'}


#########################################################################################
# PANELS
#########################################################################################


class ANIMV_UL_Action_List(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        self.use_filter_show = True
        
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon="ACTION")
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
        
        layout.label(text= ob.name, icon="POSE_HLT")
        layout.prop(props, "inplace")
        
        row = layout.row(align=True)
        for s in (0.25, 0.5, 1, 1.25, 1.5, 2):
            row.operator(ANIMV_OT_SetSpeed.bl_idname, text=str(s)).speed = s
        
        layout.template_list("ANIMV_UL_Action_List", "", bpy.data, "actions", ob, "anim_list_index")


#########################################################################################
# PROPERTIES
#########################################################################################


class ANIMV_Props(PropertyGroup):

    speed: FloatProperty(
        name="Animation Speed",
        description="Set Animation Speed",
        update = update_animation,
        default=1.0,
    )
    inplace: BoolProperty(
        name="In Place",
        description="Make Animation Inplace (WARNING: Not permanent)",
        update = update_animation,
        default=False,
    )
    action_changed_inplace: StringProperty(
        name="action_changed_innplace",
        description="Action name used to track which action is modified",
        default="",
    )
    data_path_changed_inplace: StringProperty(
        name="data_path_changed_innplace",
        description="data_path name used to track which action is modified",
        default="",
    )


#########################################################################################
# REGISTER/UNREGISTER
#########################################################################################


classes = (
    ANIMV_OT_SetSpeed,
    ANIMV_UL_Action_List,
    ANIMV_PT_Viewer,
    ANIMV_Props,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Object.anim_list_index = IntProperty(
        update = update_animation, 
        description = "Anim Viewer's highlighted action on list for this object"
    )
    bpy.types.WindowManager.animv_props = PointerProperty(
        type=ANIMV_Props,
        name="ANIMV Props",
    )


def unregister():

    del bpy.types.Object.anim_list_index

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()