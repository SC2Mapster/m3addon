# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
from .. import cm
from .. import shared


def findUnusedProjectionName(scene, prefix=''):
    usedNames = list()
    for projection in scene.m3_projections:
        usedNames.append(projection.boneName)

    counter = 1
    while True:
        suggestedName = "{prefix}{counter}".format(prefix=prefix, counter=counter)
        if suggestedName not in usedNames:
            return suggestedName
        counter += 1


class ProjectionMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_M3_projections"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout
        layout.operator("m3.projections_duplicate", text="Duplicate")


class ProjectionPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_projections"
    bl_label = "M3 Projections"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        rows = 2
        if len(scene.m3_projections) == 1:
            rows = 3
        if len(scene.m3_projections) > 1:
            rows = 5

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_projections", scene, "m3_projections", scene, "m3_projection_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.projections_add", icon='ADD', text="")
        col.operator("m3.projections_remove", icon='REMOVE', text="")

        if len(scene.m3_projections) > 0:
            col.separator()
            col.menu("OBJECT_MT_M3_projections", icon="DOWNARROW_HLT", text="")

        if len(scene.m3_projections) > 1:
            col.separator()
            col.operator("m3.projections_move", icon='TRIA_UP', text="").shift = -1
            col.operator("m3.projections_move", icon='TRIA_DOWN', text="").shift = 1

        currentIndex = scene.m3_projection_index
        if currentIndex >= 0 and currentIndex < len(scene.m3_projections):
            projection = scene.m3_projections[currentIndex]
            layout.separator()
            layout.prop(projection, 'name')
            layout.prop_search(projection, 'materialName', scene, 'm3_material_references', text="Material", icon='NONE')
            col = layout.column(align=True)
            col.prop(projection, "projectionType", text="Type")
            box = col.box()
            bcol = box.column(align=True)
            if projection.projectionType == cm.ProjectionType.orthonormal:
                bcol.prop(projection, 'depth', text="Depth")
                bcol.prop(projection, 'width', text="Width")
                bcol.prop(projection, 'height', text="Height")
            elif projection.projectionType == cm.ProjectionType.perspective:
                bcol.prop(projection, 'fieldOfView')
                bcol.prop(projection, 'aspectRatio', text="Aspect Ratio")
                bcol.prop(projection, 'near', text="Near")
                bcol.prop(projection, 'far', text="Far")

            row = layout.row()
            row.label(text='Splat Layer:')
            row.prop(projection, 'splatLayer', text='')

            row = layout.row(align=True)
            row.label(text='LOD Reduce/Cutoff:')
            row.prop(projection, 'lodReduce', text='')
            row.prop(projection, 'lodCut', text='')

            row = layout.row()
            col = row.column(align=True)
            col.label(text="Alpha Over Time:")
            col.prop(projection, 'alphaOverTimeStart', text="Start")
            col.prop(projection, 'alphaOverTimeMid', text="Middle")
            col.prop(projection, 'alphaOverTimeEnd', text="End")

            row = layout.row(align=True)
            row.label(text='Lifetime (Attack):')
            row.prop(projection, 'splatLifeTimeAttack', text='From')
            row.prop(projection, 'splatLifeTimeAttackTo', text='To')

            row = layout.row(align=True)
            row.label(text='Lifetime (Hold):')
            row.prop(projection, 'splatLifeTimeHold', text='From')
            row.prop(projection, 'splatLifeTimeHoldTo', text='To')

            row = layout.row(align=True)
            row.label(text='Lifetime (Decay):')
            row.prop(projection, 'splatLifeTimeDecay', text='From')
            row.prop(projection, 'splatLifeTimeDecayTo', text='To')

            row = layout.row()
            row.label(text=cm.M3GroupProjection.bl_rna.properties['attenuationPlaneDistance'].name)
            row.prop(projection, 'attenuationPlaneDistance', text='Start at')

            layout.label(text="Flags:")
            box = layout.box()
            col = box.column_flow()
            col.prop(projection, 'active')
            col.prop(projection, 'staticPosition')
            col.prop(projection, 'unknownFlag0x2')
            col.prop(projection, 'unknownFlag0x4')
            col.prop(projection, 'unknownFlag0x8')


class M3_PROJECTIONS_OT_add(bpy.types.Operator):
    bl_idname = 'm3.projections_add'
    bl_label = "Add Projection"
    bl_description = "Adds a projection for the export to the m3 model format"

    def invoke(self, context: bpy.context, event: bpy.types.Event):
        scene = context.scene

        projection = scene.m3_projections.add()
        projection.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_projections])

        scene.m3_projection_index = len(scene.m3_projections) - 1

        return {'FINISHED'}


class M3_PROJECTIONS_OT_remove(bpy.types.Operator):
    bl_idname = 'm3.projections_remove'
    bl_label = "Remove M3 Projection"
    bl_description = "Removes the active M3 projection"

    def invoke(self, context, event):
        scene = context.scene

        if scene.m3_projection_index >= 0:
            projection = scene.m3_projections[scene.m3_projection_index]
            shared.removeBone(scene, projection.boneName)
            scene.m3_projections.remove(scene.m3_projection_index)

            if scene.m3_projection_index != 0 or len(scene.m3_projections) == 0:
                scene.m3_projection_index -= 1

        return {'FINISHED'}


class M3_PROJECTIONS_OT_move(bpy.types.Operator):
    bl_idname = "m3.projections_move"
    bl_label = "Move M3 Projection"
    bl_description = "Moves the active M3 projection"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_projection_index

        if (ii < len(scene.m3_projections) - self.shift and ii >= -self.shift):
            scene.m3_projections.move(ii, ii + self.shift)
            scene.m3_projection_index += self.shift

        return{"FINISHED"}


class M3_PROJECTIONS_OT_duplicate(bpy.types.Operator):
    bl_idname = "m3.projections_duplicate"
    bl_label = "Duplicate M3 Projection"
    bl_description = "Duplicates the active M3 projection"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        projection = scene.m3_projections[scene.m3_projection_index]
        newProjection = scene.m3_projections.add()

        shared.copyBpyProps(newProjection, projection, skip="name")
        newProjection.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_projections], prefix=projection.name)

        scene.m3_projection_index = len(scene.m3_projections) - 1

        return {"FINISHED"}
