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


class ProjectionType:
    orthonormal = "1"
    perspective = "2"


ProjectionTypeList = [
    (ProjectionType.orthonormal, "Orthonormal", "Makes the Projector behave like a box. It will be the same width no matter how close the projector is to the target surface."),
    (ProjectionType.perspective, "Perspective", "Makes the Projector behave like a camera. The closer the projector is to the surface, the smaller the effect will be.")
]


class SplatLayer:
    material = "8"
    power = "7"
    aoe = "6"
    building = "4"
    layer3 = "3"
    layer2 = "2"
    layer1 = "1"
    layer0 = "0"
    underCreep = "12"
    hardtile = "11"


SplatLayerEnum = [
    (SplatLayer.material, "Material UI Layer", "Used for in-world effects that are part of the user interface. This includes selection circles and similar effects."),
    (SplatLayer.power, "Power Layer", "contains rarely active effects such as the Protoss power grid that should be above most other splats, but below UI."),
    (SplatLayer.aoe, "AOE Layer", "conventionally holds AOE cursors and some special spell effects."),
    (SplatLayer.building, "Building Layer", "is most often used for the dark shadow that occurs under buildings."),
    (SplatLayer.layer3, "Layer 3", "Is a generic layer that occurs above creep, that is open for use as the user sees fit. Spell effects, blast marks, or any other general case splats usually occur on a generic layer, and are adjusted freely between them to correct visual artifacts."),
    (SplatLayer.layer2, "Layer 2", "Is a generic layer that occurs above creep, that is open for use as the user sees fit. Spell effects, blast marks, or any other general case splats usually occur on a generic layer, and are adjusted freely between them to correct visual artifacts."),
    (SplatLayer.layer1, "Layer 1", "Is a generic layer that occurs above creep, that is open for use as the user sees fit. Spell effects, blast marks, or any other general case splats usually occur on a generic layer, and are adjusted freely between them to correct visual artifacts."),
    (SplatLayer.layer0, "Layer 0", "Is a generic layer that occurs above creep, that is open for use as the user sees fit. Spell effects, blast marks, or any other general case splats usually occur on a generic layer, and are adjusted freely between them to correct visual artifacts."),
    (SplatLayer.underCreep, "Under Creep Layer", "Is a general use layer that occurs below creep. It is most often used for effects that appear above roads but below creep."),
    (SplatLayer.hardtile, "Hardtile Layer", "Is the most common layer for visual additions like paint, grunge, or damage that appear to be part of the terrain texture. Roads are also drawn on this layer."),
]


def updateBoneShapeOfProjection(projection, bone, poseBone):
    if projection.projectionType == ProjectionType.orthonormal:
        untransformedPositions, faces = shared.createMeshDataForCuboid(projection.width, projection.height, projection.depth)
    else:
        # TODO create correct mesh for perspective projection
        untransformedPositions, faces = shared.createMeshDataForSphere(1.0)

    boneName = bone.name
    meshName = boneName + 'Mesh'
    shared.updateBoneShape(bone, poseBone, meshName, untransformedPositions, faces)


def selectOrCreateBoneForProjection(scene, projection):
    scene.m3_bone_visiblity_options.showProjections = True
    bone, poseBone = shared.selectOrCreateBone(scene, projection.boneName)
    updateBoneShapeOfProjection(projection, bone, poseBone)


def handleProjectionSizeChange(self, context):
    if not self.bl_update:
        return

    scene = context.scene
    if self.updateBlenderBone:
        selectOrCreateBoneForProjection(scene, self)


def handleProjectionIndexChanged(self: bpy.types.Scene, context: bpy.types.Context):
    scene = context.scene
    if scene.m3_projection_index == -1:
        return
    projection = scene.m3_projections[scene.m3_projection_index]
    selectOrCreateBoneForProjection(scene, projection)


def onUpdateName(self, context):
    if not self.bl_update:
        return

    scene = context.scene

    currentBoneName = self.boneName
    calculatedBoneName = shared.boneNameForProjection(self)

    if currentBoneName != calculatedBoneName:
        bone, armatureObject = shared.findBoneWithArmatureObject(scene, currentBoneName)
        if bone is not None:
            bone.name = calculatedBoneName
            self.boneName = bone.name
        else:
            self.boneName = calculatedBoneName

    selectOrCreateBoneForProjection(scene, self)


class M3Projection(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        options=set(), update=onUpdateName,
    )
    boneName: bpy.props.StringProperty(
        options=set(),
    )
    bl_update: bpy.props.BoolProperty(
        default=True,
    )
    materialName: bpy.props.StringProperty(
        options=set(),
    )
    projectionType: bpy.props.EnumProperty(
        default=ProjectionType.orthonormal, items=ProjectionTypeList, options=set(),
        update=handleProjectionSizeChange,
        name='Type',
    )
    fieldOfView: bpy.props.FloatProperty(
        default=45.0, options={'ANIMATABLE'},
        name='FOV',
        description='Represents the angle (in degrees) that defines the vertical bounds of the projector',
    )
    aspectRatio: bpy.props.FloatProperty(
        default=1.0, options={'ANIMATABLE'},
        name='Aspect Ratio',
    )
    near: bpy.props.FloatProperty(
        default=0.5, options={'ANIMATABLE'},
        name='Near',
    )
    far: bpy.props.FloatProperty(
        default=10.0, options={'ANIMATABLE'},
        name='Far',
    )
    depth: bpy.props.FloatProperty(
        default=10.0, options=set(), update=handleProjectionSizeChange,
        name='Depth',
    )
    width: bpy.props.FloatProperty(
        default=10.0, options=set(), update=handleProjectionSizeChange,
        name='Width',
    )
    height: bpy.props.FloatProperty(
        default=10.0, options=set(), update=handleProjectionSizeChange,
        name='Height',
    )
    alphaOverTimeStart: bpy.props.FloatProperty(
        default=0.0, min=0.0, max=1.0, options=set(), subtype="FACTOR",
        name='Alpha over time start',
    )
    alphaOverTimeMid: bpy.props.FloatProperty(
        default=1.0, min=0.0, max=1.0, options=set(), subtype="FACTOR",
        name='Alpha over time mid',
    )
    alphaOverTimeEnd: bpy.props.FloatProperty(
        default=0.0, min=0.0, max=1.0, options=set(), subtype="FACTOR",
        name='Alpha over time end',
    )
    splatLifeTimeAttack: bpy.props.FloatProperty(
        default=1.0, min=0.0, options=set(),
        name='Splat Lifetime: Attack',
    )
    splatLifeTimeAttackTo: bpy.props.FloatProperty(
        default=0.0, min=0.0, options=set(),
        name='Splat Lifetime: Attack To',
    )
    splatLifeTimeHold: bpy.props.FloatProperty(
        default=1.0, min=0.0, options=set(),
        name='Splat Lifetime: Hold',
    )
    splatLifeTimeHoldTo: bpy.props.FloatProperty(
        default=0.0, min=0.0, options=set(),
        name='Splat Lifetime: Hold To',
    )
    splatLifeTimeDecay: bpy.props.FloatProperty(
        default=1.0, min=0.0, options=set(),
        name='Splat Lifetime: Decay',
    )
    splatLifeTimeDecayTo: bpy.props.FloatProperty(
        default=0.0, min=0.0, options=set(),
        name='Splat Lifetime: Decay To',
    )
    attenuationPlaneDistance: bpy.props.FloatProperty(
        default=1.0, min=0.0, options=set(),
        name='Attenuation Plane:',
        description=f'''\
Makes it so that the splat will fade out as the surface gets further from the projection source. \
When off, the projector will be at full opacity across its entire length. \
Attenuation starts at % distance' pushes the start of the attenuation further from the projection source, \
making the splat display at full opacity for more of its range. 0 is a standard linear attenuation from the source. \
100% would be equivalent to not using attenuation at all.\
''',
    )
    active: bpy.props.BoolProperty(
        default=True, options={'ANIMATABLE'},
        name='Alive',
        description=f'''\
Makes the Projector on by default. Most static splats will have this enabled.
This may be off in the case of dynamically generated splats.
Turning off this value will trigger the splat to fade out as defined by "Decay" (Splat Lifetimes).\
''',
    )
    splatLayer: bpy.props.EnumProperty(
        default=SplatLayer.hardtile, items=SplatLayerEnum, options=set(),
        name='Splat Layer',
        description=f'''
Denotes the general sorting group of the Projector. This is used to sort overlapping splats so that everything looks correct. \
Note that Projectors that use SC2. \
SplatTerrainBake respect relative ordering with other projectors using that material type, \
but all draw 'below' splats using any other material type.

The sort order of projectors in one layer is undefined, but the sort order between layers is well defined. \
The descriptions for the values below show them in order, where the first entry draws on top of all others, \
and the last entry is below all others.\
''',
    )
    lodCut: bpy.props.EnumProperty(
        items=shared.lodEnum,
        options=set(),
        name='LOD Cut',
        description=f'''
Denotes which graphical setting level the Projector will no longer be displayed at. \
If critical for gameplay, leaving this at "None" is prudent. Otherwise, it is useful for performance scaling.\
''',
    )
    lodReduce: bpy.props.EnumProperty(
        items=shared.lodEnum,
        options=set(),
        name='LOD Reduction',
        description=f'''
Denotes which graphical setting the Projector can potentially be not shown at if there are too many splats on screen. \
It is more critical to be judicious with allowing splats to disappear here, \
as it is best to leave room available for gameplay-critical splats.\
''',
    )
    staticPosition: bpy.props.BoolProperty(
        options=set(),
        name='Static Position',
    )
    unknownFlag0x2: bpy.props.BoolProperty(
        options=set(),
    )
    unknownFlag0x4: bpy.props.BoolProperty(
        options=set(),
    )
    unknownFlag0x8: bpy.props.BoolProperty(
        options=set(),
    )
