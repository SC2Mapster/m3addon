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
from .. import shared


class ExportM3ContainerVersion:
    V23 = "23"
    V26 = "26"
    V29 = "29"


ExportContainerM3VersionList = [
    (ExportM3ContainerVersion.V23, "V23 (*stable*)", "Super old, but somewhat working. It was default export format till 2021."),
    (ExportM3ContainerVersion.V26, "V26 (beta)", "Semi old, but with more features available, however it hasn't been tested thoroughly."),
    (ExportM3ContainerVersion.V29, "V29 (alpha)", "Newest available for SC2. WIP.")
]

animationExportAmount = [
    (shared.exportAmountAllAnimations, "All animations", "All animations will be exported"),
    (shared.exportAmountCurrentAnimation, "Current animation", "Only the current animation will be exported"),
    # Possible future additions: CURRENT_FRAME or FIRST_FRAME
    (shared.exportAmountNoAnimations, "None", "No animations at all")
]


class M3ExportOptions(bpy.types.PropertyGroup):
    path: bpy.props.StringProperty(name="path", default="ExportedModel.m3", options=set())
    modlVersion: bpy.props.EnumProperty(name="M3 Version", default=ExportM3ContainerVersion.V26, items=ExportContainerM3VersionList, options=set())
    animationExportAmount: bpy.props.EnumProperty(name="Animations", default=shared.exportAmountAllAnimations, items=animationExportAmount, options=set())


class M3ImportContentPreset:
    Everything = "EVERYTHING"
    MeshMaterialsRig = "MESH_MATERIALS_RIG"
    MeshMaterials = "MESH_MATERIALS"
    Custom = "CUSTOM"
    # CustomInteractive = "CUSTOM_INTERACTIVE"


contentImportPresetList = [
    (M3ImportContentPreset.Everything, "Everything", "Import everything included in the m3 file"),
    (M3ImportContentPreset.MeshMaterialsRig, "Mesh, materials and rigging", "Import the mesh, materials and rigging. When using this preset you'll likely want to merge imported rig with existing armature."),
    (M3ImportContentPreset.MeshMaterials, "Mesh with materials only", "Import the mesh with its m3 materials only"),
    # (M3ImportContentPreset.Custom, "Custom", "Customize what's being imported"),
]


class M3ImportContent(bpy.types.PropertyGroup):
    mesh: bpy.props.BoolProperty(
        name="Mesh",
        default=True,
        options=set()
    )
    materials: bpy.props.BoolProperty(
        name="Materials",
        default=True,
        options=set()
    )
    bones: bpy.props.BoolProperty(
        name="Bones",
        default=True,
        options=set()
    )
    rigging: bpy.props.BoolProperty(
        name="Rigging",
        description="Includes vertex groups & weight painting",
        default=True,
        options=set()
    )
    cameras: bpy.props.BoolProperty(
        name="Cameras",
        default=True,
        options=set()
    )
    fuzzyHitTests: bpy.props.BoolProperty(
        name="Fuzzy hit tests",
        default=True,
        options=set()
    )
    tightHitTest: bpy.props.BoolProperty(
        name="Tight hit test",
        default=True,
        options=set()
    )
    particleSystems: bpy.props.BoolProperty(
        name="Particle systems",
        default=True,
        options=set()
    )
    ribbons: bpy.props.BoolProperty(
        name="Ribbons",
        default=True,
        options=set()
    )
    forces: bpy.props.BoolProperty(
        name="Forces",
        default=True,
        options=set()
    )
    rigidBodies: bpy.props.BoolProperty(
        name="Rigid bodies",
        default=True,
        options=set()
    )
    lights: bpy.props.BoolProperty(
        name="Lights",
        default=True,
        options=set()
    )
    billboardBehaviors: bpy.props.BoolProperty(
        name="Billboard behaviors",
        default=True,
        options=set()
    )
    attachmentPoints: bpy.props.BoolProperty(
        name="Attachment points",
        default=True,
        options=set()
    )
    projections: bpy.props.BoolProperty(
        name="Projections",
        default=True,
        options=set()
    )
    warps: bpy.props.BoolProperty(
        name="Warps",
        default=True,
        options=set()
    )


def handleContentPresetChange(options, context: bpy.types.Context):
    options = options # type: M3ImportOptions
    content: M3ImportContent = options.content
    # content.mesh = True


class M3ImportOptions(bpy.types.PropertyGroup):
    path: bpy.props.StringProperty(name="path", default="", options=set())
    rootDirectory: bpy.props.StringProperty(name="rootDirectory", default="", options=set())
    generateBlenderMaterials: bpy.props.BoolProperty(default=True, options=set())
    applySmoothShading: bpy.props.BoolProperty(default=True, options=set())
    markSharpEdges: bpy.props.BoolProperty(default=True, options=set())
    recalculateRestPositionBones: bpy.props.BoolProperty(default=False, options=set())
    teamColor: bpy.props.FloatVectorProperty(
        default=(1.0, 0.0, 0.0), min=0.0, max=1.0, name="team color", size=3, subtype="COLOR", options=set(),
        description="Team color place holder used for generated blender materials"
    )
    contentPreset: bpy.props.EnumProperty(
        name="Import preset mode",
        description="Content import mode",
        default="EVERYTHING",
        items=contentImportPresetList,
        options=set(),
        update=handleContentPresetChange,
    )
    content: bpy.props.PointerProperty(
        type=M3ImportContent,
    )
    armatureObject: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Armature",
        description="Defines which armature object should be used when importing rigging. If unset, a new one will be created.",
        options=set(),
        poll=lambda self, obj: obj.type == 'ARMATURE' and obj.data is not self
    )
