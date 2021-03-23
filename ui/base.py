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
import bpy_extras
from ..common import mlog
from ..cm import M3ImportContentPreset
from .. import m3export
from .. import m3import

class ExportPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_quickExport"
    bl_label = "M3 Quick Export"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        scene = context.scene
        self.layout.prop(scene.m3_export_options, "path", text="")
        self.layout.operator("m3.quick_export", text="Export As M3")
        ExportPanel.draw_layout(self.layout, scene)

    @classmethod
    def draw_layout(cls, layout: bpy.types.UILayout, scene: bpy.types.Scene):
        layout.prop(scene.m3_export_options, "modlVersion")
        layout.prop(scene.m3_export_options, "animationExportAmount")


class M3_OT_export(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    """Export a M3 file"""
    bl_idname = "m3.export"
    bl_label = "Export M3 Model"
    bl_options = {"UNDO"}

    filename_ext = ".m3"
    filter_glob: bpy.props.StringProperty(default="*.m3", options={"HIDDEN"})

    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Path of the file that should be created",
        maxlen=1024, default=""
    )

    def execute(self, context):
        scene = context.scene
        scene.m3_export_options.path = self.properties.filepath
        return m3export.export(scene, self, self.properties.filepath)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        ExportPanel.draw_layout(self.layout, context.scene)


class M3_OT_quickExport(bpy.types.Operator):
    bl_idname = "m3.quick_export"
    bl_label = "Quick Export"
    bl_description = "Exports the model to the specified m3 path without asking further questions"

    def invoke(self, context, event):
        scene = context.scene
        fileName = scene.m3_export_options.path
        return m3export.export(scene, self, fileName)


class ImportPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_quickImport"
    bl_label = "M3 Import"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene.m3_import_options, "path", text="M3 File")
        ImportPanel.draw_layout(layout, scene)
        layout.operator("m3.quick_import", text="Import M3")
        layout.operator("m3.generate_blender_materials", text="Generate Blender Materials")

    @classmethod
    def draw_content_import(cls, layout: bpy.types.UILayout, scene: bpy.types.Scene):
        layout.prop(scene.m3_import_options.content, "mesh")
        layout.prop(scene.m3_import_options.content, "materials")
        layout.prop(scene.m3_import_options.content, "bones")
        layout.prop(scene.m3_import_options.content, "rigging")
        layout.prop(scene.m3_import_options.content, "cameras")
        layout.prop(scene.m3_import_options.content, "fuzzyHitTests")
        layout.prop(scene.m3_import_options.content, "tightHitTest")
        layout.prop(scene.m3_import_options.content, "particleSystems")
        layout.prop(scene.m3_import_options.content, "ribbons")
        layout.prop(scene.m3_import_options.content, "forces")
        layout.prop(scene.m3_import_options.content, "rigidBodies")
        layout.prop(scene.m3_import_options.content, "lights")
        layout.prop(scene.m3_import_options.content, "billboardBehaviors")
        layout.prop(scene.m3_import_options.content, "attachmentPoints")
        layout.prop(scene.m3_import_options.content, "projections")
        layout.prop(scene.m3_import_options.content, "warps")

    @classmethod
    def draw_layout(cls, layout: bpy.types.UILayout, scene: bpy.types.Scene):
        layout.prop(scene.m3_import_options, "contentPreset")
        if scene.m3_import_options.contentPreset == M3ImportContentPreset.Custom:
            ImportPanel.draw_content_import(layout.box().column(heading="Content to import"), scene)
        layout.prop(scene.m3_import_options, "armatureObject")

        layout.separator()
        layout.prop(scene.m3_import_options, "rootDirectory", text="Root Directory")
        layout.prop(scene.m3_import_options, "generateBlenderMaterials", text="Generate Blender Materials At Import")
        layout.prop(scene.m3_import_options, "applySmoothShading", text="Apply Smooth Shading")
        layout.prop(scene.m3_import_options, "markSharpEdges", text="Mark sharp edges")
        layout.prop(scene.m3_import_options, "teamColor", text="Team Color")


class M3_OT_import(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    """Load a M3 file"""
    bl_idname = "m3.import"
    bl_label = "Import M3"
    bl_options = {"UNDO"}

    filename_ext = ".m3"
    filter_glob: bpy.props.StringProperty(default="*.m3;*.m3a", options={"HIDDEN"})

    filepath: bpy.props.StringProperty(
        name="File Path",
        description="File path used for importing the simple M3 file",
        maxlen=1024,
        default=""
    )

    def execute(self, context):
        mlog.debug("Import %s" % self.properties.filepath)
        scene = context.scene
        scene.m3_import_options.path = self.properties.filepath
        m3import.importM3BasedOnM3ImportOptions(scene)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        ImportPanel.draw_layout(self.layout, context.scene)


class M3_OT_quickImport(bpy.types.Operator):
    bl_idname = "m3.quick_import"
    bl_label = "Quick Import"
    bl_description = "Imports the model to the specified m3 path without asking further questions"

    def invoke(self, context, event):
        scene = context.scene
        m3import.importM3BasedOnM3ImportOptions(scene)
        return {"FINISHED"}
