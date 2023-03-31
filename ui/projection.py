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


class ProjectionMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_M3_projections"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout
        shared.draw_collection_op_generic(layout, 'duplicate', 'm3_projections', 'm3_projection_index', text='Duplicate')


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

        shared.draw_collection_list(layout, 'm3_projections', 'm3_projection_index', menu_id=ProjectionMenu.bl_idname)

        if scene.m3_projection_index < 0:
            return

        projection = scene.m3_projections[scene.m3_projection_index]
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
        row.label(text=cm.M3Projection.bl_rna.properties['attenuationPlaneDistance'].name)
        row.prop(projection, 'attenuationPlaneDistance', text='Start at')

        layout.label(text="Flags:")
        box = layout.box()
        col = box.column_flow()
        col.prop(projection, 'active')
        col.prop(projection, 'staticPosition')
        col.prop(projection, 'unknownFlag0x2')
        col.prop(projection, 'unknownFlag0x4')
        col.prop(projection, 'unknownFlag0x8')
