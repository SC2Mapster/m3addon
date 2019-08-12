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
        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_projections", scene, "m3_projections", scene, "m3_projection_index", rows=2)

        col = row.column(align=True)
        col.operator("m3.projections_add", icon='ADD', text="")
        col.operator("m3.projections_remove", icon='REMOVE', text="")
        currentIndex = scene.m3_projection_index
        if currentIndex >= 0 and currentIndex < len(scene.m3_projections):
            projection = scene.m3_projections[currentIndex]
            layout.separator()
            split = layout.split()
            col = split.column()

            col.prop(projection, 'name')
            col.prop_search(projection, 'materialName', scene, 'm3_material_references', text="Material", icon='NONE')

            box = layout.box()
            col = box.column()
            col.label(text="Projection type")
            col = box.column_flow()
            col.prop(projection, "projectionType", expand=True)
            col = box.column()

            if projection.projectionType == cm.ProjectionType.orthonormal:
                col.prop(projection, 'depth', text="Depth")
                col.prop(projection, 'width', text="Width")
                col.prop(projection, 'height', text="Height")
            elif projection.projectionType == cm.ProjectionType.perspective:
                col.prop(projection, 'fieldOfView')
                col.prop(projection, 'aspectRatio', text="Aspect Ratio")
                col.prop(projection, 'near', text="Near")
                col.prop(projection, 'far', text="Far")
            split = layout.split()
            col = split.column()

            col.label(text="Alpha Over Time:")
            col.prop(projection, 'alphaOverTimeStart', text="Start")
            col.prop(projection, 'alphaOverTimeMid', text="Middle")
            col.prop(projection, 'alphaOverTimeEnd', text="End")
            split = layout.split()
            col = split.column()

            col.label(text='Splat Lifetimes (Attack):')
            col = col.column_flow(columns=2, align=True)
            col.prop(projection, 'splatLifeTimeAttack', text='From')
            col.prop(projection, 'splatLifeTimeAttackTo', text='To')
            split = layout.split()
            col = split.column()

            col.label(text='Splat Lifetimes (Hold):')
            col = col.column_flow(columns=2, align=True)
            col.prop(projection, 'splatLifeTimeHold', text='From')
            col.prop(projection, 'splatLifeTimeHoldTo', text='To')
            split = layout.split()
            col = split.column()

            col.label(text='Splat Lifetimes (Decay):')
            col = col.column_flow(columns=2, align=True)
            col.prop(projection, 'splatLifeTimeDecay', text='From')
            col.prop(projection, 'splatLifeTimeDecayTo', text='To')
            split = layout.split()
            col = split.column()

            col.label(text=cm.M3GroupProjection.bl_rna.properties['attenuationPlaneDistance'].name)
            col.prop(projection, 'attenuationPlaneDistance', text='Start at')
            split = layout.split()
            col = split.column()

            col = col.column_flow(columns=2, align=True)
            col.label(text='Active')
            col.prop(projection, 'active', text='')
            split = layout.split()
            col = split.column()

            col = col.column_flow(columns=2, align=True)
            col.label(text='Splat layer')
            col.prop(projection, 'splatLayer', text='')
            split = layout.split()
            col = split.column()

            col = col.column_flow(columns=2, align=True)
            col.label(text=cm.M3GroupProjection.bl_rna.properties['lodReduce'].name)
            col.prop(projection, 'lodReduce', text='')
            split = layout.split()
            col = split.column()

            col = col.column_flow(columns=2, align=True)
            col.label(text=cm.M3GroupProjection.bl_rna.properties['lodCut'].name)
            col.prop(projection, 'lodCut', text='')
            split = layout.split()
            col = split.column()

            col.label(text="Flags")
            box = layout.box()
            col = box.column_flow()
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
        boneName = self.findUnusedName(scene)

        projection = scene.m3_projections.add()
        projection.name = boneName

        scene.m3_projection_index = len(scene.m3_projections) - 1

        return {'FINISHED'}

    def findUnusedName(self, scene):
        usedNames = list()
        for projection in scene.m3_projections:
            usedNames.append(projection.boneName)

        counter = 1
        while True:
            suggestedName = "SC2Projector%03d" % counter
            if suggestedName not in usedNames:
                return suggestedName
            counter += 1


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
            scene.m3_projection_index -= 1

        return {'FINISHED'}
