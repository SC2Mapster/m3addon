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
from . import shared


blenderMaterialsFieldNames = {
    shared.standardMaterialTypeIndex: "m3_standard_materials",
    shared.displacementMaterialTypeIndex: "m3_displacement_materials",
    shared.compositeMaterialTypeIndex: "m3_composite_materials",
    shared.terrainMaterialTypeIndex: "m3_terrain_materials",
    shared.volumeMaterialTypeIndex: "m3_volume_materials",
    shared.creepMaterialTypeIndex: "m3_creep_materials",
    shared.volumeNoiseMaterialTypeIndex: "m3_volume_noise_materials",
    shared.stbMaterialTypeIndex: "m3_stb_materials",
    # TODO: reflection material
    shared.lensFlareMaterialTypeIndex: "m3_lens_flare_materials",
    shared.bufferMaterialTypeIndex: "m3_buffer_materials",
}

uvSourceList = [
    ("0", "Default", "First UV layer of mesh or generated whole image UVs for particles"),
    ("1", "UV Layer 2", "Second UV layer which can be used for decals"),
    ("2", "Ref Cubic Env", "For Env. Layer: Reflective Cubic Environment"),
    ("3", "Ref Spherical Env", "For Env. Layer: Reflective Spherical Environemnt"),
    ("4", "Planar Local z", "Planar Local z"),
    ("5", "Planar World z", "Planar World z"),
    ("6", "Animated Particle UV", "The flip book of the particle system is used to determine the UVs"),
    ("7", "Cubic Environment", "For Env. Layer: Cubic Environment"),
    ("8", "Spherical Environment", "For Env. Layer: Spherical Environment"),
    ("9", "UV Layer 3", "UV Layer 3"),
    ("10", "UV Layer 4", "UV Layer 4"),
    ("11", "Planar Local X", "Planar Local X"),
    ("12", "Planar Local Y", "Planar Local Y"),
    ("13", "Planar World X", "Planar World X"),
    ("14", "Planar World Y", "Planar World Y"),
    ("15", "Screen space", "Screen space"),
    ("16", "Tri Planar World", "Tri Planar World"),
    ("17", "Tri Planar World Local", "Tri Planar Local"),
    ("18", "Tri Planar World Local Z", "Tri Planar World Local Z")
]

rttChannelList = [
    ("-1", "None", "None"),
    ("0", "Layer 1", "Render To Texture Layer 1"),
    ("1", "Layer 2", "Render To Texture Layer 2"),
    ("2", "Layer 3", "Render To Texture Layer 3"),
    ("3", "Layer 4", "Render To Texture Layer 4"),
    ("4", "Layer 5", "Render To Texture Layer 5"),
    ("5", "Layer 6", "Render To Texture Layer 6"),
    ("6", "Layer 7", "Render To Texture Layer 7"),
]

colorChannelSettingList = [
    (shared.colorChannelSettingRGB, "RGB", "Use red, green and blue color channel"),
    (shared.colorChannelSettingRGBA, "RGBA", "Use red, green, blue and alpha channel"),
    (shared.colorChannelSettingA, "Alpha Only", "Use alpha channel only"),
    (shared.colorChannelSettingR, "Red Only", "Use red color channel only"),
    (shared.colorChannelSettingG, "Green Only", "Use green color channel only"),
    (shared.colorChannelSettingB, "Blue Only", "Use blue color channel only")
]

fresnelTypeList = [
    ("0", "Disabled", "Fresnel is disabled"),
    ("1", "Enabled", "Strength of layer is based on fresnel formula"),
    ("2", "Enabled; Inverted", "Strenth of layer is based on inverted fresnel formula")
]

videoModeList = [
    ("0", "Loop", "Loop"),
    ("1", "Hold", "Hold")
]


materialTexmapType = [
    ("0", "Bitmap", "Bitmap"),
    ("1", "Color", "Color")
]


class M3Material(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="name", default="Material", options=set())
    materialType: bpy.props.IntProperty(options=set())
    materialIndex: bpy.props.IntProperty(options=set())


class M3MaterialLayer(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(default="Material Layer")
    imagePath: bpy.props.StringProperty(name="image path", default="", options=set())
    unknownbd3f7b5d: bpy.props.IntProperty(name="unknownbd3f7b5d", default=-1, options=set())
    color: bpy.props.FloatVectorProperty(name="color", default=(1.0, 1.0, 1.0, 1.0), min=0.0, max=1.0, size=4, subtype="COLOR", options={"ANIMATABLE"})
    textureWrapX: bpy.props.BoolProperty(options=set(), default=True)
    textureWrapY: bpy.props.BoolProperty(options=set(), default=True)
    invertColor: bpy.props.BoolProperty(options=set(), default=False)
    clampColor: bpy.props.BoolProperty(options=set(), default=False)
    colorEnabled: bpy.props.EnumProperty(items=materialTexmapType)
    uvSource: bpy.props.EnumProperty(items=uvSourceList, options=set(), default="0")
    brightMult: bpy.props.FloatProperty(name="bright. mult.", options={"ANIMATABLE"}, default=1.0)
    uvOffset: bpy.props.FloatVectorProperty(name="uv offset", default=(0.0, 0.0), size=2, subtype="XYZ", options={"ANIMATABLE"})
    uvAngle: bpy.props.FloatVectorProperty(name="uv offset", default=(0.0, 0.0, 0.0), size=3, subtype="XYZ", options={"ANIMATABLE"})
    uvTiling: bpy.props.FloatVectorProperty(name="uv tiling", default=(1.0, 1.0), size=2, subtype="XYZ", options={"ANIMATABLE"})
    triPlanarOffset: bpy.props.FloatVectorProperty(name="tri planer offset", default=(0.0, 0.0, 0.0), size=3, subtype="XYZ", options={"ANIMATABLE"})
    triPlanarScale: bpy.props.FloatVectorProperty(name="tri planer scale", default=(1.0, 1.0, 1.0), size=3, subtype="XYZ", options={"ANIMATABLE"})
    flipBookRows: bpy.props.IntProperty(name="flipBookRows", default=0, options=set())
    flipBookColumns: bpy.props.IntProperty(name="flipBookColumns", default=0, options=set())
    flipBookFrame: bpy.props.IntProperty(name="flipBookFrame", default=0, options={"ANIMATABLE"})
    midtoneOffset: bpy.props.FloatProperty(name="midtone offset", options={"ANIMATABLE"}, description="Can be used to make dark areas even darker so that only the bright regions remain")
    brightness: bpy.props.FloatProperty(name="brightness", options={"ANIMATABLE"}, default=1.0)
    rttChannel: bpy.props.EnumProperty(items=rttChannelList, options=set(), default="-1")
    colorChannelSetting: bpy.props.EnumProperty(items=colorChannelSettingList, options=set(), default=shared.colorChannelSettingRGB)
    fresnelType: bpy.props.EnumProperty(items=fresnelTypeList, options=set(), default="0")
    invertedFresnel: bpy.props.BoolProperty(options=set())
    fresnelExponent: bpy.props.FloatProperty(default=4.0, options=set())
    fresnelMin: bpy.props.FloatProperty(default=0.0, options=set())
    fresnelMax: bpy.props.FloatProperty(default=1.0, options=set())
    fresnelMaskX: bpy.props.FloatProperty(options=set(), min=0.0, max=1.0)
    fresnelMaskY: bpy.props.FloatProperty(options=set(), min=0.0, max=1.0)
    fresnelMaskZ: bpy.props.FloatProperty(options=set(), min=0.0, max=1.0)
    fresnelRotationYaw: bpy.props.FloatProperty(subtype="ANGLE", options=set())
    fresnelRotationPitch: bpy.props.FloatProperty(subtype="ANGLE", options=set())
    fresnelLocalTransform: bpy.props.BoolProperty(options=set(), default=False)
    fresnelDoNotMirror: bpy.props.BoolProperty(options=set(), default=False)
    videoFrameRate: bpy.props.IntProperty(options=set(), default=24)
    videoStartFrame: bpy.props.IntProperty(options=set(), default=0)
    videoEndFrame: bpy.props.IntProperty(options=set(), default=-1)
    videoMode: bpy.props.EnumProperty(items=videoModeList, options=set(), default="0")
    videoSyncTiming: bpy.props.BoolProperty(options=set())
    videoPlay: bpy.props.BoolProperty(name="videoPlay", options={"ANIMATABLE"}, default=True)
    videoRestart: bpy.props.BoolProperty(name="videoRestart", options={"ANIMATABLE"}, default=True)


def getMaterial(scene, materialTypeIndex, materialIndex) -> M3Material:
    try:
        blenderFieldName = blenderMaterialsFieldNames[materialTypeIndex]
    except KeyError:
        # unsupported material
        return None
    materialsList = getattr(scene, blenderFieldName)
    return materialsList[materialIndex]
