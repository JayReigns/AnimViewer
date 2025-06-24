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
from bpy.props import IntProperty, FloatProperty, EnumProperty, StringProperty, BoolProperty, BoolVectorProperty, PointerProperty
from bpy.types import Operator, Menu, UIList, Panel, PropertyGroup, AddonPreferences

LOCATION_CONSTRAINT_NAME = "AnimV Inplace Constraint"

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
    if bpy.app.version >= (4, 4, 0):
        ob.animation_data.action_slot = action.slots[0]


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

    lim_loc_constr = ob.constraints.get(LOCATION_CONSTRAINT_NAME)

    # inplace
    if any(props.inplace_axes):
        if not lim_loc_constr:
            lim_loc_constr = ob.constraints.new('LIMIT_LOCATION')
            lim_loc_constr.name = LOCATION_CONSTRAINT_NAME
        
        lim_loc_constr.use_min_x = props.inplace_axes[0]
        lim_loc_constr.use_max_x = props.inplace_axes[0]
        lim_loc_constr.min_x = 0.0
        lim_loc_constr.max_x = 0.0
        lim_loc_constr.use_min_y = props.inplace_axes[1]
        lim_loc_constr.use_max_y = props.inplace_axes[1]
        lim_loc_constr.min_y = 0.0
        lim_loc_constr.max_y = 0.0
        lim_loc_constr.use_min_z = props.inplace_axes[2]
        lim_loc_constr.use_max_z = props.inplace_axes[2]
        lim_loc_constr.min_z = 0.0
        lim_loc_constr.max_z = 0.0
        lim_loc_constr.owner_space = 'WORLD'
        lim_loc_constr.influence = 1.0

    elif lim_loc_constr:
        # remove existing inplace constraint
        for c in ob.constraints:
            if c.name == LOCATION_CONSTRAINT_NAME:
                ob.constraints.remove(c)


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
        layout.prop( props, "inplace_axes" , toggle = True) 

        row = layout.row(align=True)
        row.label(text="Speed:")
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
    inplace_axes: BoolVectorProperty(  
        name = "Inplace", 
        description = "Limit translations in these axes (Uses Constraints)",
        update = update_animation,
        default = (False, False, False),
        subtype = 'XYZ',
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