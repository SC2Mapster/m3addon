#!/usr/bin/python3
# -*- coding: utf-8 -*-

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

from typing import Iterable
import bpy
import mathutils
import random
import math
# from bpy_extras import io_utils
from os import path
from bpy_extras import image_utils
from . import im

lodEnum = [
    ("0", "None", "LOD has no effect"),
    ("1", "Low", "LOD cutoff or reduction takes effect if graphics are Low"),
    ("2", "Medium", "LOD cutoff or reduction takes effect if graphics are Medium"),
    ("3", "High", "LOD cutoff or reduction takes effect if graphics are High"),
    ("4", "Ultra", "LOD cutoff or reduction takes effect if graphics are Ultra")
]

materialNames = [
    "No Material",
    "Standard",
    "Displacement",
    "Composite",
    "Terrain",
    "Volume",
    "Unknown [6]",
    "Creep",
    "Volume Noise",
    "Splat Terrain Bake",
    "Reflection",
    "Lens Flare",
    "Shader (MADD)",
]
standardMaterialTypeIndex = 1
displacementMaterialTypeIndex = 2
compositeMaterialTypeIndex = 3
terrainMaterialTypeIndex = 4
volumeMaterialTypeIndex = 5
creepMaterialTypeIndex = 7
volumeNoiseMaterialTypeIndex = 8
stbMaterialTypeIndex = 9
reflectionMaterialMaterialTypeIndex = 10
lensFlareMaterialTypeIndex = 11
bufferMaterialTypeIndex = 12

emissionAreaTypePoint = "0"
emissionAreaTypePlane = "1"
emissionAreaTypeSphere = "2"
emissionAreaTypeCuboid = "3"
emissionAreaTypeCylinder = "4"
emissionAreaTypeDisc = "5"
emissionAreaTypeMesh = "6"

attachmentVolumeNone = "-1"
attachmentVolumeCuboid = "0"
attachmentVolumeSphere = "1"
attachmentVolumeCapsule = "2"

forceShapeSphere = "0"
forceShapeCylinder = "1"
forceShapeBox = "2"
forceShapeHemisphere = "3"
forceShapeConeDome = "4"

lightTypePoint = "1"
lightTypeSpot = "2"

physicsJointSphere = "0"
physicsJointRevolute = "1"
physicsJointCone = "2"
physicsJointWeld = "3"

colorChannelSettingRGB = "0"
colorChannelSettingRGBA = "1"
colorChannelSettingA = "2"
colorChannelSettingR = "3"
colorChannelSettingG = "4"
colorChannelSettingB = "5"

defaultDepthBlendFalloff = 0.2  # default if it is enabled

tightHitTestBoneName = "HitTestTight"

rotFixMatrix = mathutils.Matrix(((0, 1, 0, 0),
                                (-1, 0, 0, 0),
                                 (0, 0, 1, 0),
                                 (0, 0, 0, 1)))
rotFixMatrixInverted = rotFixMatrix.transposed()

animFlagsForAnimatedProperty = 6

star2ParticlePrefix = "Star2Part"
star2RibbonPrefix = "Star2Ribbon"
star2ForcePrefix = "Star2Force"
star2ProjectionPrefix = "Star2 projector"
# Ref_ is the bone prefix for attachment points without volume and
# the prefix for all attachment point names (for volume attachment point names too)
attachmentPointPrefix = "Ref_"
attachmentVolumePrefix = "Vol_"
star2WarpPrefix = "SC2VertexWarp"
animObjectIdModel = "MODEL"
animObjectIdArmature = "ARMATURE"
animObjectIdScene = "SCENE"
lightPrefixMap = {"1": "Star2Omni", "2": "Star2Spot"}

layerFieldNameToNameMap = {
    "diffuseLayer": "Diffuse",
    "decalLayer": "Decal",
    "specularLayer": "Specular",
    "glossLayer": "Gloss",
    "emissiveLayer": "Emissive",
    "emissive2Layer": "Emissive 2",
    "evioLayer": "Evio",
    "evioMaskLayer": "Evio Mask",
    "alphaMaskLayer": "Alpha Mask",
    "alphaMask2Layer": "Alpha Mask 2",
    "normalLayer": "Normal",
    "heightLayer": "Height",
    "colorDefiningLayer": "Color Defining Layer",
    "normalBlendMask1": "Normal Blending Mask 1",
    "normalBlendMask2": "Normal Blending Mask 2",
    "normalBlendNormal1": "Normal Blending Normal 1",
    "normalBlendNormal2": "Normal Blending Normal 2",
    "lightMapLayer": "Light Map",
    "ambientOcclussionLayer": "Ambient Occlussion",
    "strengthLayer": "Strength",
    "terrainLayer": "Terrain",
    "colorLayer": "Color",
    "noise1Layer": "Noise 1",
    "noise2Layer": "Noise 2",
    "creepLayer": "Creep",
    "unknownLayer1": "Unknown Layer 1",
    "unknownLayer2": "Unknown Layer 2",
}

exportAmountAllAnimations = "ALL_ANIMATIONS"
exportAmountCurrentAnimation = "CURRENT_ANIMATION"
exportAmountNoAnimations = "NO_ANIMATIONS"


class ExportError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def getLayerNameFromFieldName(fieldName):
    name = layerFieldNameToNameMap.get(fieldName)
    if name is None:
        name = fieldName
    return name


def layerFieldNamesOfM3Material(m3Material):
    for field in m3Material.structureDescription.fields:
        if hasattr(field, "referenceStructureDescription"):
            if field.historyOfReferencedStructures.name == "LAYR":
                yield field.name


def copyBpyProps(dst, src, skip=[]):
    assert type(dst) == type(src)
    props = type(dst).__annotations__.keys()
    # TODO: should probably filter the annotations list to bpy.types.Property
    for k in props:
        if k in skip:
            continue
        setattr(dst, k, getattr(src, k))
    return dst


def setDefaultValue(defaultAction, path, index, value):
    curve = None
    for c in defaultAction.fcurves:
        if c.data_path == path and c.array_index == index:
            curve = c
            break
    if curve is None:
        curve = defaultAction.fcurves.new(path, index=index)
    keyFrame = curve.keyframe_points.insert(0, value)
    keyFrame.interpolation = "CONSTANT"


def findUnusedPropItemName(scene, propGroups=[], suggestedNames=[], prefix=""):
    usedNames = set()
    for propGroup in propGroups:
        for propItem in propGroup:
            usedNames.add(propItem.name)

    counterNum = 1
    unusedName = None
    while unusedName is None:
        for suggestedName in suggestedNames:
            if suggestedName not in usedNames:
                return suggestedName

        if counterNum < 10:
            counter = "0" + str(counterNum)
        else:
            counter = str(counterNum)

        if prefix == "":
            suggestedName = "{counter}".format(counter=counter)
        else:
            suggestedName = "{prefix} {counter}".format(prefix=prefix, counter=counter)

        if suggestedName not in usedNames:
            unusedName = suggestedName
        counterNum += 1

    return unusedName


def toValidBoneName(name):
    maxLength = 63
    return name[:maxLength]


def boneNameForAttachmentPoint(attachmentPoint):
    bonePrefix = attachmentPointPrefix if attachmentPoint.volumeType == "-1" else attachmentVolumePrefix
    return bonePrefix + attachmentPoint.name


def attachmentPointNameFromBoneName(boneName):
    if boneName.startswith(attachmentPointPrefix):
        return boneName[len(attachmentPointPrefix):]
    elif boneName.startswith(attachmentVolumePrefix):
        return boneName[len(attachmentVolumePrefix):]
    else:
        return boneName


def boneNameForParticleSystem(particleSystem):
    return toValidBoneName(star2ParticlePrefix + particleSystem.name)


def boneNameForRibbon(ribbon):
    return toValidBoneName(star2RibbonPrefix + ribbon.name)


def boneNameForForce(force):
    return toValidBoneName(star2ForcePrefix + force.name)


def boneNameForLight(light):
    lightPrefix = lightPrefixMap.get(light.lightType)
    return toValidBoneName(lightPrefix + light.name)


def boneNameForProjection(projection):
    return toValidBoneName(star2ProjectionPrefix + projection.name)


def boneNameForWarp(warp):
    return toValidBoneName(star2WarpPrefix + warp.name)


def iterateArmatureObjects(scene):
    for obj in scene.objects:
        if obj.type == "ARMATURE":
            if obj.data is not None:
                yield obj


def findArmatureObjectForNewBone(scene):
    for obj in iterateArmatureObjects(scene):
        return obj
    return None


def findBoneWithArmatureObject(scene, boneName):
    for armatureObject in iterateArmatureObjects(scene):
        armature = armatureObject.data
        bone = armature.bones.get(boneName)
        if bone is not None:
            return (bone, armatureObject)
    return (None, None)


def scaleVectorToMatrix(scaleVector):
    matrix = mathutils.Matrix()
    matrix[0][0] = scaleVector[0]
    matrix[1][1] = scaleVector[1]
    matrix[2][2] = scaleVector[2]
    return matrix


def locRotScaleMatrix(location, rotation, scale):
    """ Important: rotation must be a normalized quaternion """
    # to_matrix() only works properly with normalized quaternions.
    result = rotation.to_matrix().to_4x4()
    result.col[0] *= scale.x
    result.col[1] *= scale.y
    result.col[2] *= scale.z
    result.translation = location
    return result


def selectBone(scene, boneName):
    bone, armature = findBoneWithArmatureObject(scene, boneName)
    if bone is None or armature is None:
        return

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action='DESELECT')

    armature.select_set(True)
    scene.view_layers[0].objects.active = armature

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='POSE')

    for b in armature.data.bones:
        b.select = False

    bone.select = True
    armature.data.bones.active = bone


def removeBone(scene, boneName):
    "removes the given bone if it exists"
    bone, armatureObject = findBoneWithArmatureObject(scene, boneName)
    if bone is None or armatureObject is None:
        return

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action='DESELECT')

    armatureObject.select_set(True)
    scene.view_layers[0].objects.active = armatureObject

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='EDIT')

    armature = armatureObject.data
    edit_bone = armature.edit_bones[boneName]
    armature.edit_bones.remove(edit_bone)

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='POSE')


def selectOrCreateBone(scene, boneName):
    "Returns the bone and it's pose variant"
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action='DESELECT')
    bone, armatureObject = findBoneWithArmatureObject(scene, boneName)
    boneExists = bone is not None
    if boneExists:
        armature = armatureObject.data
        armatureObject.select_set(True)
        scene.view_layers[0].objects.active = armatureObject
    else:
        armatureObject = findArmatureObjectForNewBone(scene)
        if armatureObject is None:
            armature = bpy.data.armatures.new(name="Armature")
            armatureObject = bpy.data.objects.new("Armature", armature)
            scene.collection.objects.link(armatureObject)
        else:
            armature = armatureObject.data
        armatureObject.select_set(True)
        scene.view_layers[0].objects.active = armatureObject
        bpy.ops.object.mode_set(mode='EDIT')
        editBone = armature.edit_bones.new(name=boneName)
        editBone.head = (0, 0, 0)
        editBone.tail = (1, 0, 0)

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='POSE')

    for boneOfArmature in armature.bones:
        isBoneToSelect = boneOfArmature.name == boneName
        boneOfArmature.select_head = isBoneToSelect
        boneOfArmature.select_tail = isBoneToSelect
        boneOfArmature.select = isBoneToSelect
    armature.bones.active = bone

    scene.view_layers[0].objects.active = armatureObject
    armatureObject.select_set(True)
    for currentBone in armature.bones:
        currentBone.select = currentBone.name == boneName

    poseBone = armatureObject.pose.bones[boneName]
    bone = armatureObject.data.bones[boneName]
    return (bone, poseBone)


def selectBoneIfItExists(scene, boneName):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action='DESELECT')
    bone, armatureObject = findBoneWithArmatureObject(scene, boneName)
    if bone is None:
        return
    armature = armatureObject.data
    armatureObject.select_set(True)
    scene.view_layers[0].objects.active = armatureObject
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='POSE')
    scene.view_layers[0].objects.active = armatureObject
    armatureObject.select_set(True)
    for currentBone in armature.bones:
        currentBone.select = currentBone.name == boneName


def selectBonesIfTheyExist(scene, boneNames):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action='DESELECT')
    bones = []
    armatureObjects = []
    for ii, boneName in enumerate(boneNames):
        r = findBoneWithArmatureObject(scene, boneName)
        bones.append(r[0])
        armatureObjects.append(r[1])
    for ii, bone in enumerate(bones):
        if bone is None:
            continue
        armature = armatureObjects[ii].data
        armatureObjects[ii].select_set(True)
        scene.view_layers[0].objects.active = armatureObjects[ii]
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='POSE')
        scene.view_layers[0].objects.active = armatureObjects[ii]
        armatureObjects[ii].select_set(True)
        for currentBone in armature.bones:
            currentBone.select = currentBone.name in boneNames


class UniqueNameFinder:

    def __init__(self):
        self.usedNames = set()

    def markNamesOfCollectionAsUsed(self, collection):
        for item in collection:
            self.usedNames.add(item.name)

    def findNameAndMarkAsUsedLike(self, wantedName):
        nameWithoutNumberSuffix = self.removeNumberSuffix(wantedName)
        namePrefix = nameWithoutNumberSuffix[:25]
        # Suffixes of sc2 animations most often start with 01
        # For other objects it doesn't hurt do it the same, and often it is even like that
        suffixNumber = 1
        name = wantedName
        while name in self.usedNames:
            name = "%s %02d" % (namePrefix, suffixNumber)
            suffixNumber += 1
        self.usedNames.add(name)
        return name

    def removeNumberSuffix(self, name):
        lastIndex = len(name) - 1
        index = lastIndex
        while(index > 0 and name[index] in ["0", "1", "2", "3", "4", "5", "6", "7", "9"]):
            index -= 1
        name = name[:index + 1]
        if name.endswith(" ") or name.endswith("_"):
            name = name[:-1]
        return name


def dump(obj, title=None):
    o: List[str] = []
    o.append("%s" % (title if title else obj))
    if hasattr(obj, '__iter__'):
        c = int(len(obj) / 10) + 1
        for i, x in enumerate(obj):
            o.append(dump(x, "[%0*d]" % (c, i)))
    else:
        for attr in dir(obj):
            if hasattr(obj, attr):
                o.append("  %16s = %s" % (attr, getattr(obj, attr)))
    return "\n".join(o)


def isVideoFilePath(filePath):
    return filePath.endswith(".ogv") or filePath.endswith(".ogg")


def sqr(x):
    return x * x


def smoothQuaternionTransition(previousQuaternion, quaternionToFix):
    sumOfSquares = sqr(quaternionToFix.x - previousQuaternion.x) + sqr(quaternionToFix.y - previousQuaternion.y) + sqr(quaternionToFix.z - previousQuaternion.z) + sqr(quaternionToFix.w - previousQuaternion.w)
    sumOfSquaresMinus = sqr(-quaternionToFix.x - previousQuaternion.x) + sqr(-quaternionToFix.y - previousQuaternion.y) + sqr(-quaternionToFix.z - previousQuaternion.z) + sqr(-quaternionToFix.w - previousQuaternion.w)
    if sumOfSquaresMinus < sumOfSquares:
        quaternionToFix.negate()


def floatInterpolationFunction(leftInterpolationValue, rightInterpolationValue, rightFactor):
    leftFactor = 1.0 - rightFactor
    return leftInterpolationValue * leftFactor + rightInterpolationValue * rightFactor


def vectorInterpolationFunction(leftInterpolationValue, rightInterpolationValue, rightFactor):
    return leftInterpolationValue.lerp(rightInterpolationValue, rightFactor)


def quaternionInterpolationFunction(leftInterpolationValue, rightInterpolationValue, rightFactor):
    return leftInterpolationValue.slerp(rightInterpolationValue, rightFactor)


def floatsAlmostEqual(floatExpected, floatActual):
    delta = abs(floatExpected - floatActual)
    return delta < 0.00001


def vectorsAlmostEqual(vectorExpected, vectorActual):
    diff = vectorExpected - vectorActual
    return diff.length < 0.00001


def quaternionsAlmostEqual(q0, q1):
    distanceSqr = sqr(q0.x - q1.x) + sqr(q0.y - q1.y) + sqr(q0.z - q1.z) + sqr(q0.w - q1.w)
    return distanceSqr < sqr(0.00001)


def simplifyFloatAnimationWithInterpolation(timeValuesInMS, values):
    return simplifyAnimationWithInterpolation(timeValuesInMS, values, floatInterpolationFunction, floatsAlmostEqual)


def simplifyVectorAnimationWithInterpolation(timeValuesInMS, vectors):
    return simplifyAnimationWithInterpolation(timeValuesInMS, vectors, vectorInterpolationFunction, vectorsAlmostEqual)


def simplifyQuaternionAnimationWithInterpolation(timeValuesInMS, vectors):
    return simplifyAnimationWithInterpolation(timeValuesInMS, vectors, quaternionInterpolationFunction, quaternionsAlmostEqual)


def simplifyAnimationWithInterpolation(timeValuesInMS, values, interpolationFunction, almostEqualFunction):
    if len(timeValuesInMS) < 2:
        return timeValuesInMS, values
    leftTimeInMS = timeValuesInMS[0]
    leftValue = values[0]
    currentTimeInMS = timeValuesInMS[1]
    currentValue = values[1]
    newTimeValuesInMS = [leftTimeInMS]
    newValues = [leftValue]
    for rightTimeInMS, rightValue in zip(timeValuesInMS[2:], values[2:]):
        timeSinceLeftTime = currentTimeInMS - leftTimeInMS
        intervalLength = rightTimeInMS - leftTimeInMS
        rightFactor = timeSinceLeftTime / intervalLength
        expectedValue = interpolationFunction(leftValue, rightValue, rightFactor)
        if almostEqualFunction(expectedValue, currentValue):
            # ignore current value since it's interpolatable:
            pass
        else:
            newTimeValuesInMS.append(currentTimeInMS)
            newValues.append(currentValue)
            leftTimeInMS = currentTimeInMS
            leftValue = currentValue
        currentValue = rightValue
        currentTimeInMS = rightTimeInMS
    newTimeValuesInMS.append(timeValuesInMS[-1])
    newValues.append(values[-1])
    return newTimeValuesInMS, newValues


def findMeshObjects(scene: bpy.types.Scene) -> Iterable[bpy.types.Object]:
    for currentObject in scene.objects:
        if currentObject.type == 'MESH':
            yield currentObject


def convertM3UVSourceValueToUVLayerName(mesh, uvSource):
    """ Can return None"""
    if uvSource == "0":
        uvLayerIndex = 0
    elif uvSource == "1":
        uvLayerIndex = 1
    elif uvSource == "9":
        uvLayerIndex = 2
    elif uvSource == "10":
        uvLayerIndex = 3
    else:
        return None

    if uvLayerIndex < len(mesh.uv_layers):
        return mesh.uv_layers[uvLayerIndex].name
    else:
        return None


def createImageObjetForM3MaterialLayer(blenderM3Layer, directoryList):
    if blenderM3Layer is None:
        return None

    if (blenderM3Layer.imagePath == "") or (blenderM3Layer.imagePath is None):
        return None

    imagePath = blenderM3Layer.imagePath
    blenderImage: bpy.types.Image = None

    if path.isabs(imagePath):
        if path.isfile(imagePath):
            blenderImage = image_utils.load_image(imagePath, check_existing=True)
        else:
            imagePath = path.basename(imagePath)

    if not blenderImage:
        targetList = []
        for x in directoryList:
            targetList.append(path.join(x, path.basename(imagePath)))
            targetList.append(path.join(x, imagePath))

        for x in targetList:
            if path.isfile(x):
                blenderImage = image_utils.load_image(x, check_existing=True)
                break

        if not blenderImage:
            print("Failed to load a texture %s. The following paths have been tested: %s" % (imagePath, targetList))
            blenderImage = image_utils.load_image(imagePath, place_holder=True, check_existing=True)

    return blenderImage


def getStandardMaterialOrNull(scene, mesh):
    if mesh.m3_material_name == "":
        return None
    materialReference = scene.m3_material_references[mesh.m3_material_name]
    materialType = materialReference.materialType
    materialIndex = materialReference.materialIndex
    if materialType not in [standardMaterialTypeIndex, compositeMaterialTypeIndex]:
        print("Material generation is only supported for starard materials, but not for material %s" % m3MaterialFieldNames[materialType])
        return None
    if materialType == compositeMaterialTypeIndex:
        compositing_material = scene.m3_composite_materials[materialIndex]
        for key in compositing_material.sections.keys():
            ref = scene.m3_material_references[key]
            if ref.materialType == standardMaterialTypeIndex:
                return scene.m3_standard_materials[ref.materialIndex]
            return None
    else:
        return scene.m3_standard_materials[materialIndex]


def createUVNodesFromM3LayerAndReturnSocket(mesh, tree, blenderM3Layer):
    """ Returns a socket that provies UVs or None"""
    uvLayerName = convertM3UVSourceValueToUVLayerName(mesh, blenderM3Layer.uvSource)
    if uvLayerName is None:
        return None
    uvAttributeNode = tree.nodes.new("ShaderNodeAttribute")
    uvAttributeNode.attribute_name = uvLayerName

    outputNode = uvAttributeNode.outputs["Vector"]

    if (not blenderM3Layer.textureWrapX) and (not blenderM3Layer.textureWrapY):
        mappingNode = tree.nodes.new("ShaderNodeMapping")
        mappingNode.vector_type = "POINT"
        tree.links.new(outputNode, mappingNode.inputs["Vector"])
        outputNode = mappingNode.outputs["Vector"]
    else:
        if (not blenderM3Layer.textureWrapX) or (not blenderM3Layer.textureWrapY):
            print("Note: Generated cycles material won't have correct texture clamp. One sided texture wrap is not implemented yet")
    return outputNode


def createTextureNodeForM3MaterialLayer(mesh, tree, blenderM3Layer, directoryList):
    image = createImageObjetForM3MaterialLayer(blenderM3Layer, directoryList)
    if image is None:
        return None

    textureNode = tree.nodes.new("ShaderNodeTexImage")
    textureNode.image = image

    uvSocket = createUVNodesFromM3LayerAndReturnSocket(mesh, tree, blenderM3Layer)
    if uvSocket is not None:
        tree.links.new(uvSocket, textureNode.inputs["Vector"])

    return textureNode


def determineTextureDirectoryList(scene):
    textureDirectories = []
    textureDirectories.append(scene.m3_import_options.rootDirectory)

    if path.isfile(scene.m3_import_options.path):
        modelDirectory = path.dirname(scene.m3_import_options.path)
        textureDirectories.append(modelDirectory)
    return textureDirectories


def createNormalMapNode(mesh, tree, standardMaterial, directoryList):

    normalLayer = standardMaterial.layers[getLayerNameFromFieldName("normalLayer")]
    normalTextureNode = createTextureNodeForM3MaterialLayer(mesh, tree, normalLayer, directoryList)
    if normalTextureNode is None:
        return None
    normalTextureSeparateRGBNode = tree.nodes.new("ShaderNodeSeparateRGB")
    tree.links.new(normalTextureNode.outputs["Color"], normalTextureSeparateRGBNode.inputs["Image"])

    # Invert Green of normal texture
    normalTextureGreenInvertNode = tree.nodes.new("ShaderNodeMath")
    normalTextureGreenInvertNode.operation = "SUBTRACT"
    normalTextureGreenInvertNode.inputs[0].default_value = 1.0
    tree.links.new(normalTextureSeparateRGBNode.outputs["G"], normalTextureGreenInvertNode.inputs[1])

    # Bring green of normal texture to range [-0.5,0.5]
    normalTextureGreenSubZeroDotFiveNode = tree.nodes.new("ShaderNodeMath")
    normalTextureGreenSubZeroDotFiveNode.operation = "SUBTRACT"
    normalTextureGreenSubZeroDotFiveNode.inputs[1].default_value = 0.5
    tree.links.new(normalTextureGreenInvertNode.outputs["Value"], normalTextureGreenSubZeroDotFiveNode.inputs[0])

    # Bring green of normal texture to range [-1,1]
    normalTextureGreenMul2Node = tree.nodes.new("ShaderNodeMath")
    normalTextureGreenMul2Node.operation = "ADD"
    tree.links.new(normalTextureGreenSubZeroDotFiveNode.outputs["Value"], normalTextureGreenMul2Node.inputs[0])
    tree.links.new(normalTextureGreenSubZeroDotFiveNode.outputs["Value"], normalTextureGreenMul2Node.inputs[1])

    # Calculate (normal green in range [-1,1]) ^ 2
    normalTextureGreenPower2Node = tree.nodes.new("ShaderNodeMath")
    normalTextureGreenPower2Node.operation = "MULTIPLY"
    tree.links.new(normalTextureGreenMul2Node.outputs["Value"], normalTextureGreenPower2Node.inputs[0])
    tree.links.new(normalTextureGreenMul2Node.outputs["Value"], normalTextureGreenPower2Node.inputs[1])

    # Bring alpha of normal texture to range [-0.5,0.5]
    normalTextureAlphaSubZeroDotFiveNode = tree.nodes.new("ShaderNodeMath")
    normalTextureAlphaSubZeroDotFiveNode.operation = "SUBTRACT"
    normalTextureAlphaSubZeroDotFiveNode.inputs[1].default_value = 0.5
    tree.links.new(normalTextureNode.outputs["Alpha"], normalTextureAlphaSubZeroDotFiveNode.inputs[0])

    # Bring alpha of normal texture to range [-1,1]
    normalTextureAlphaMul2Node = tree.nodes.new("ShaderNodeMath")
    normalTextureAlphaMul2Node.operation = "MULTIPLY"
    tree.links.new(normalTextureAlphaSubZeroDotFiveNode.outputs["Value"], normalTextureAlphaMul2Node.inputs[0])
    tree.links.new(normalTextureAlphaSubZeroDotFiveNode.outputs["Value"], normalTextureAlphaMul2Node.inputs[1])

    # Calculate (normal alpha in range [-1,1]) ^ 2
    normalTextureAlphaPower2Node = tree.nodes.new("ShaderNodeMath")
    normalTextureAlphaPower2Node.operation = "MULTIPLY"
    tree.links.new(normalTextureAlphaMul2Node.outputs["Value"], normalTextureAlphaPower2Node.inputs[0])
    tree.links.new(normalTextureAlphaMul2Node.outputs["Value"], normalTextureAlphaPower2Node.inputs[1])

    # Calculate (green in range [-1,1])^2 + (alpha in range [-1,1]) ^ 2
    normalTextureAddGreenAndAlphaNode = tree.nodes.new("ShaderNodeMath")
    normalTextureAddGreenAndAlphaNode.operation = "ADD"
    tree.links.new(normalTextureGreenPower2Node.outputs["Value"], normalTextureAddGreenAndAlphaNode.inputs[0])
    tree.links.new(normalTextureAlphaPower2Node.outputs["Value"], normalTextureAddGreenAndAlphaNode.inputs[1])

    # Calculate (new blue)^2 == 1 - (new red)^2 + (new green)^2
    # == 1- ((green in range [-1,1])^2 to (alpha in range [-1,1])^2)
    normalTextureNewBluePower2Node = tree.nodes.new("ShaderNodeMath")
    normalTextureNewBluePower2Node.operation = "SUBTRACT"
    normalTextureNewBluePower2Node.inputs[0].default_value = 1.0
    tree.links.new(normalTextureAddGreenAndAlphaNode.outputs["Value"], normalTextureNewBluePower2Node.inputs[1])

    # Calculate new blue in range [0,1] via = sqrt (1- ((green in range [-1,1])^2 to (alpha in range [-1,1])^2))
    # Based on the assumtion that sqrt(r^2+ g^2 + b^2) == 1
    normalTextureNewBlueNode = tree.nodes.new("ShaderNodeMath")
    normalTextureNewBlueNode.operation = "POWER"
    normalTextureNewBlueNode.inputs[1].default_value = 0.5
    tree.links.new(normalTextureNewBluePower2Node.outputs["Value"], normalTextureNewBlueNode.inputs[0])

    normalTextureConvertedNode = tree.nodes.new("ShaderNodeCombineRGB")
    tree.links.new(normalTextureNode.outputs["Alpha"], normalTextureConvertedNode.inputs["R"])
    tree.links.new(normalTextureGreenInvertNode.outputs["Value"], normalTextureConvertedNode.inputs["G"])
    tree.links.new(normalTextureNewBlueNode.outputs["Value"], normalTextureConvertedNode.inputs["B"])

    normalMapNode = tree.nodes.new('ShaderNodeNormalMap')
    normalMapNode.space = "TANGENT"
    normalMapNode.inputs["Strength"].default_value = 0.5
    normalMapNode.uv_map = convertM3UVSourceValueToUVLayerName(mesh, normalLayer.uvSource)
    tree.links.new(normalTextureConvertedNode.outputs["Image"], normalMapNode.inputs["Color"])

    return normalMapNode


def createCyclesMaterialForMeshObject(scene, meshObject):
    mesh = meshObject.data
    standardMaterial = getStandardMaterialOrNull(scene, mesh)
    if standardMaterial is None:
        return

    realMaterial = bpy.data.materials.new(standardMaterial.name)
    directoryList = determineTextureDirectoryList(scene)

    diffuseLayer = standardMaterial.layers[getLayerNameFromFieldName("diffuseLayer")]
    specularLayer = standardMaterial.layers[getLayerNameFromFieldName("specularLayer")]

    realMaterial.use_nodes = True
    tree = realMaterial.node_tree
    tree.links.clear()
    tree.nodes.clear()

    diffuseTextureNode = createTextureNodeForM3MaterialLayer(mesh, tree, diffuseLayer, directoryList)
    if diffuseTextureNode is not None:
        if diffuseLayer.colorChannelSetting == colorChannelSettingRGBA:
            diffuseTeamColorMixNode = tree.nodes.new("ShaderNodeMixRGB")
            diffuseTeamColorMixNode. blend_type = "MIX"
            teamColor = scene.m3_import_options.teamColor
            diffuseTeamColorMixNode.inputs["Color1"].default_value = (teamColor[0], teamColor[1], teamColor[2], 1.0)
            tree.links.new(diffuseTextureNode.outputs["Alpha"], diffuseTeamColorMixNode.inputs["Fac"])
            tree.links.new(diffuseTextureNode.outputs["Color"], diffuseTeamColorMixNode.inputs["Color2"])
            finalDiffuseColorOutputSocket = diffuseTeamColorMixNode.outputs["Color"]
        else:
            finalDiffuseColorOutputSocket = diffuseTextureNode.outputs["Color"]
    else:
        rgbNode = tree.nodes.new("ShaderNodeRGB")
        rgbNode.outputs[0].default_value = (0, 0, 0, 1)
        finalDiffuseColorOutputSocket = rgbNode.outputs[0]

    decalLayer = standardMaterial.layers[getLayerNameFromFieldName("decalLayer")]
    decalTextureNode = createTextureNodeForM3MaterialLayer(mesh, tree, decalLayer, directoryList)
    if decalTextureNode is not None:
        decalAddingNode = tree.nodes.new("ShaderNodeMixRGB")
        decalAddingNode. blend_type = "SCREEN"
        tree.links.new(decalTextureNode.outputs["Alpha"], decalAddingNode.inputs["Fac"])
        tree.links.new(decalTextureNode.outputs["Color"], decalAddingNode.inputs["Color2"])
        tree.links.new(finalDiffuseColorOutputSocket, decalAddingNode.inputs["Color1"])
        finalDiffuseColorOutputSocket = decalAddingNode.outputs["Color"]

    normalMapNode = createNormalMapNode(mesh, tree, standardMaterial, directoryList)
    diffuseShaderNode = tree.nodes.new("ShaderNodeBsdfDiffuse")
    if normalMapNode is not None:
        tree.links.new(normalMapNode.outputs["Normal"], diffuseShaderNode.inputs["Normal"])
    tree.links.new(finalDiffuseColorOutputSocket, diffuseShaderNode.inputs["Color"])
    finalShaderOutputSocket = diffuseShaderNode.outputs["BSDF"]

    specularTextureNode = createTextureNodeForM3MaterialLayer(mesh, tree, specularLayer, directoryList)

    glossyShaderNode.inputs["Roughness"].default_value = 0.2
    if specularTextureNode is not None:
        glossyShaderNode = tree.nodes.new("ShaderNodeBsdfGlossy")
        glossyShaderNode.distribution = "BECKMANN"
        if normalMapNode is not None:
            tree.links.new(normalMapNode.outputs["Normal"], glossyShaderNode.inputs["Normal"])
        tree.links.new(specularTextureNode.outputs["Color"], glossyShaderNode.inputs["Color"])

        mixShaderNode = tree.nodes.new("ShaderNodeMixShader")
        tree.links.new(specularTextureNode.outputs["Color"], mixShaderNode.inputs["Fac"])
        tree.links.new(finalShaderOutputSocket, mixShaderNode.inputs[1])
        tree.links.new(glossyShaderNode.outputs["BSDF"], mixShaderNode.inputs[2])
        finalShaderOutputSocket = mixShaderNode.outputs["Shader"]
    else:
        glossyShaderNode.inputs["Specular"].default_value = 0.1

    emissiveLayer = standardMaterial.layers[getLayerNameFromFieldName("emissiveLayer")]
    emissiveTextureNode = createTextureNodeForM3MaterialLayer(mesh, tree, emissiveLayer, directoryList)
    if emissiveTextureNode is not None:
        emissiveShaderNode = tree.nodes.new("ShaderNodeEmission")
        emissiveShaderNode.inputs[1].default_value = 10.0  # Strength
        tree.links.new(emissiveTextureNode.outputs["Color"], emissiveShaderNode.inputs["Color"])
        print("Adding emissive to %s" % standardMaterial.name)
        mixShaderNode = tree.nodes.new("ShaderNodeMixShader")
        tree.links.new(emissiveTextureNode.outputs["Color"], mixShaderNode.inputs["Fac"])
        tree.links.new(finalShaderOutputSocket, mixShaderNode.inputs[1])
        tree.links.new(emissiveShaderNode.outputs["Emission"], mixShaderNode.inputs[2])
        finalShaderOutputSocket = mixShaderNode.outputs["Shader"]

    alphaLayer = standardMaterial.layers[getLayerNameFromFieldName("alphaMaskLayer")]
    alphaTextureNode = createTextureNodeForM3MaterialLayer(mesh, tree, alphaLayer, directoryList)
    if alphaTextureNode is not None and alphaLayer.colorChannelSetting in [colorChannelSettingA, colorChannelSettingR, colorChannelSettingG, colorChannelSettingB]:
        transparencyShaderNode = tree.nodes.new("ShaderNodeBsdfTransparent")

        mixShaderNode = tree.nodes.new("ShaderNodeMixShader")
        tree.links.new(transparencyShaderNode.outputs["BSDF"], mixShaderNode.inputs[1])
        tree.links.new(finalShaderOutputSocket, mixShaderNode.inputs[2])
        if alphaLayer.colorChannelSetting == colorChannelSettingA:
            tree.links.new(alphaTextureNode.outputs["Alpha"], mixShaderNode.inputs["Fac"])
        else:
            separateRGBNode = tree.nodes.new("ShaderNodeSeparateRGB")
            tree.links.new(alphaTextureNode.outputs["Color"], separateRGBNode.inputs["Image"])

            if alphaLayer.colorChannelSetting == colorChannelSettingR:
                tree.links.new(separateRGBNode.outputs["R"], mixShaderNode.inputs["Fac"])
            elif alphaLayer.colorChannelSetting == colorChannelSettingG:
                tree.links.new(separateRGBNode.outputs["G"], mixShaderNode.inputs["Fac"])
            elif alphaLayer.colorChannelSetting == colorChannelSettingB:
                tree.links.new(separateRGBNode.outputs["B"], mixShaderNode.inputs["Fac"])
            else:
                raise Exception("alpha texture setting not handled properly earilier")
        finalShaderOutputSocket = mixShaderNode.outputs["Shader"]

    outputNode = tree.nodes.new("ShaderNodeOutputMaterial")
    outputNode.location = (500.0, 000.0)
    tree.links.new(finalShaderOutputSocket, outputNode.inputs["Surface"])

    layoutInputNodesOf(tree)

    # Remove old materials:
    while len(mesh.materials) > 0:
        mesh.materials.pop(0, update_data=True)

    mesh.materials.append(realMaterial)


def createNodeNameToInputNodesMap(tree):
    nodeNameToInputNodesMap = {}
    for link in tree.links:
        inputNodes = nodeNameToInputNodesMap.get(link.to_node.name)
        if inputNodes is None:
            inputNodes = set()
            nodeNameToInputNodesMap[link.to_node.name] = inputNodes
        inputNodes.add(link.from_node)
    return nodeNameToInputNodesMap


def createNodeNameToOutputNodesMap(tree):
    nodeNameToOutputNodesMap = {}
    for link in tree.links:
        outputNodes = nodeNameToOutputNodesMap.get(link.from_node.name)
        if outputNodes is None:
            outputNodes = set()
            nodeNameToOutputNodesMap[link.from_node.name] = outputNodes
        outputNodes.add(link.to_node)
    return nodeNameToOutputNodesMap


nodeTypeToHeightMap = {
    'NORMAL_MAP': 148,
    'MATH': 145,
    'ATTRIBUTE': 116,
    'SEPRGB': 112,
    'COMBRGB': 115,
    'MIX_RGB': 164,
    'TEX_IMAGE': 226,
    'OUTPUT_MATERIAL': 87,
    'BSDF_DIFFUSE': 112,
    'BSDF_GLOSSY': 144,
    'MIX_SHADER': 112,
    'MAPPING': 270,
    'BSDF_TRANSPARENT': 69,
    'RGB': 177,
    'EMISSION': 93,
}


def getHeightOfNewNode(node):
    # due to a blender 2.71 bug the dimensions are 0 for newly created nodes
    # due to a blender 2.71 bug the height is always 100.0
    return nodeTypeToHeightMap.get(node.type, node.height)


def layoutInputNodesOf(tree):
    horizontalDistanceBetweenNodes = 200
    verticalDistanceBetweenNodes = 50

    nodeNameToInputNodesMap = createNodeNameToInputNodesMap(tree)
    nodeNameToOutputNodesMap = createNodeNameToOutputNodesMap(tree)

    # Fix x positions of nodes:
    namesOfNodesToCheck = set(n.name for n in tree.nodes)
    while len(namesOfNodesToCheck) > 0:
        nodeName = namesOfNodesToCheck.pop()
        node = tree.nodes[nodeName]
        inputNodes = nodeNameToInputNodesMap.get(nodeName)
        if inputNodes is not None:
            for inputNode in inputNodes:
                xBasedOnNode = node.location[0] - inputNode.width - horizontalDistanceBetweenNodes
                inputNode.location[0] = min(inputNode.location[0], xBasedOnNode)
                namesOfNodesToCheck.add(inputNode.name)

    xLinkCountNameTuples = list()
    for node in tree.nodes:
        linkCount = 0
        inputNodes = nodeNameToInputNodesMap.get(node.name)
        if inputNodes is not None:
            linkCount += len(inputNodes)
        outputNodes = nodeNameToOutputNodesMap.get(node.name)
        if outputNodes is not None:
            linkCount += len(outputNodes)

        xLinkCountNameTuples.append((node.location[0], linkCount, node.name))
    xLinkCountNameTuples.sort(reverse=True)

    nodesWithFinalPosition = []
    for x, linkCount, name in xLinkCountNameTuples:
        node = tree.nodes[name]
        outputNodes = nodeNameToOutputNodesMap.get(name)
        if outputNodes is not None and len(outputNodes) > 0:
            ySum = 0
            for outputNode in outputNodes:
                ySum += outputNode.location[1]
            perfectY = ySum / len(outputNodes)
        else:
            perfectY = node.location[1]

        width = node.width
        height = getHeightOfNewNode(node)
        xCollisionNodes = []
        for otherNode in nodesWithFinalPosition:
            oX = otherNode.location[0]
            oWidth = node.width
            oIsRight = (oX >= x + width)
            oIsLeft = (oX <= x - oWidth)
            xCollision = not (oIsRight or oIsLeft)
            if xCollision:
                xCollisionNodes.append(otherNode)

        yLowerThanWished = perfectY
        yHigherThanWished = perfectY
        goodYPicked = False
        while not goodYPicked:
            if abs(yLowerThanWished - perfectY) < abs(yHigherThanWished - perfectY):
                yPicked = yLowerThanWished
            else:
                yPicked = yHigherThanWished
            goodYPicked = True
            for otherNode in xCollisionNodes:
                oY = otherNode.location[1]
                oHeight = getHeightOfNewNode(otherNode)
                oIsHigher = oY >= yPicked + oHeight + verticalDistanceBetweenNodes
                oIsLower = yPicked >= oY + height + verticalDistanceBetweenNodes
                collision = not (oIsLower or oIsHigher)
                if collision:
                    goodYPicked = False
                    if yPicked == yLowerThanWished:
                        yLowerThanWished = oY - oHeight - verticalDistanceBetweenNodes
                    if yPicked == yHigherThanWished:
                        yHigherThanWished = oY + height + verticalDistanceBetweenNodes
                    break
        node.location[1] = yPicked
        nodesWithFinalPosition.append(node)


def createBlenderMaterialForMeshObject(scene, meshObject):
    if scene.render.engine != 'BLENDER_EEVEE':
        scene.render.engine = 'BLENDER_EEVEE'
    im.material.createMaterialForMesh(scene, meshObject.data)
    # createCyclesMaterialForMeshObject(scene, meshObject)


def createBlenderMaterialsFromM3Materials(scene):
    for meshObject in findMeshObjects(scene):
        createBlenderMaterialForMeshObject(scene, meshObject)


def composeMatrix(location, rotation, scale):
    locMatrix = mathutils.Matrix.Translation(location)
    rotationMatrix = rotation.to_matrix().to_4x4()
    scaleMatrix = mathutils.Matrix()
    for i in range(3):
        scaleMatrix[i][i] = scale[i]
    return locMatrix @ rotationMatrix @ scaleMatrix


def getLongAnimIdOf(objectId, animPath):
    if objectId == animObjectIdScene and animPath.startswith("m3_boundings"):
        return objectId + "m3_boundings"
    return objectId + animPath


def getRandomAnimIdNotIn(animIdSet):
    maxValue = 0x0fffffff
    unusedAnimId = random.randint(1, maxValue)
    while unusedAnimId in animIdSet:
        unusedAnimId = random.randint(1, maxValue)
    return unusedAnimId


def createHiddenMeshObject(name, untransformedPositions, faces, matrix):
    mesh = bpy.data.meshes.new(name)
    meshObject = bpy.data.objects.new(name, mesh)
    meshObject.location = (0, 0, 0)

    transformedPositions = []
    for v in untransformedPositions:
        transformedPositions.append(matrix @ mathutils.Vector(v))

    mesh.from_pydata(transformedPositions, [], faces)

    # mesh.vertices.add(len(transformedPositions))
    # mesh.vertices.foreach_set("co", io_utils.unpack_list(transformedPositions))

    # mesh.loop_triangles.add(len(faces))
    # mesh.loop_triangles.foreach_set("vertices", io_utils.unpack_face_list(faces))

    mesh.update(calc_edges=True)
    return meshObject


def setBoneVisibility(scene, boneName, visibility):
    bone, armatureObject = findBoneWithArmatureObject(scene, boneName)
    boneExists = bone is not None
    if boneExists:
        bone.hide = not visibility


def updateBoneShapeOfShapeObject(shapeObject, bone, poseBone):
    cubeShapeConstant = "0"
    sphereShapeConstant = "1"
    capsuleShapeConstant = "2"
    if shapeObject.shape == capsuleShapeConstant:
        radius = shapeObject.size0
        height = shapeObject.size1
        untransformedPositions, faces = createMeshDataForCapsule(radius, height)
    elif shapeObject.shape == sphereShapeConstant:
        radius = shapeObject.size0
        untransformedPositions, faces = createMeshDataForSphere(radius)
    elif shapeObject.shape == cubeShapeConstant:
        sizeX, sizeY, sizeZ = 2 * shapeObject.size0, 2 * shapeObject.size1, 2 * shapeObject.size2
        untransformedPositions, faces = createMeshDataForCuboid(sizeX, sizeY, sizeZ)

    matrix = composeMatrix(shapeObject.offset, shapeObject.rotationEuler, shapeObject.scale)
    meshName = 'ShapeObjectBoneMesh'
    updateBoneShape(bone, poseBone, meshName, untransformedPositions, faces, matrix)


def updateBoneShapeOfParticleSystem(particleSystem, bone, poseBone):
    emissionAreaType = particleSystem.emissionAreaType
    if emissionAreaType == emissionAreaTypePoint:
        untransformedPositions, faces = createMeshDataForSphere(0.02)
    elif emissionAreaType == emissionAreaTypePlane:
        length = particleSystem.emissionAreaSize[0]
        width = particleSystem.emissionAreaSize[1]
        height = 0
        untransformedPositions, faces = createMeshDataForCuboid(length, width, height)
    elif emissionAreaType == emissionAreaTypeSphere:
        radius = particleSystem.emissionAreaRadius
        untransformedPositions, faces = createMeshDataForSphere(radius)
    elif emissionAreaType == emissionAreaTypeCuboid:
        length = particleSystem.emissionAreaSize[0]
        width = particleSystem.emissionAreaSize[1]
        height = particleSystem.emissionAreaSize[2]
        untransformedPositions, faces = createMeshDataForCuboid(length, width, height)
    elif emissionAreaType == emissionAreaTypeCylinder:
        radius = particleSystem.emissionAreaRadius
        height = particleSystem.emissionAreaSize[2]
        untransformedPositions, faces = createMeshDataForCylinder(radius, height)
    elif emissionAreaType == emissionAreaTypeDisc:
        radius = particleSystem.emissionAreaRadius
        height = 0.0
        untransformedPositions, faces = createMeshDataForCylinder(radius, height)
    elif emissionAreaType == emissionAreaTypeMesh:
        untransformedPositions, faces = [], []
        # Create a sphere for each point:
        for spawnPoint in particleSystem.spawnPoints:
            loc = spawnPoint.location
            size = 0.01
            subPositions, subFaces = createMeshDataForCuboid(size, size, size)
            # subPositions = [(0.0, 0.0, 0.0), (0.0, 0.02, 0.0), (0.02, 0.0, 0.0)]
            # subFaces = [(0,1,2)]
            subPositionsAtLoc = []
            for subPos in subPositions:
                subPositionsAtLoc.append((subPos[0] + loc.x, subPos[1] + loc.y, subPos[2] + loc.z))
            subFacesFixed = [[fe + len(untransformedPositions) for fe in f] for f in subFaces]
            untransformedPositions.extend(subPositionsAtLoc)
            faces.extend(subFacesFixed)

    else:
        untransformedPositions, faces = createMeshDataForSphere(0.02)

    boneName = particleSystem.boneName
    meshName = boneName + 'Mesh'
    updateBoneShape(bone, poseBone, meshName, untransformedPositions, faces)


def updateBoneShapeOfRibbon(ribbon, bone, poseBone):
    # radius scale seem to be the diameter
    startRadius = ribbon.size[0] / 2
    untransformedPositions, faces = createMeshDataForCuboid(startRadius, 0.0, 0.0)

    # untransformedPositions, faces = createMeshDataForSphere(0.02)
    # TODO create the correct ribbon meshes

    boneName = ribbon.boneName
    meshName = boneName + 'Mesh'
    updateBoneShape(bone, poseBone, meshName, untransformedPositions, faces)


def updateBoneShapeOfAttachmentPoint(attachmentPoint, bone, poseBone):
    volumeType = attachmentPoint.volumeType
    if volumeType == attachmentVolumeNone:
        untransformedPositions, faces = createAttachmentPointSymbolMesh()
    elif volumeType == attachmentVolumeCuboid:
        length = 2 * attachmentPoint.volumeSize0
        width = 2 * attachmentPoint.volumeSize1
        height = 2 * attachmentPoint.volumeSize2
        untransformedPositions, faces = createMeshDataForCuboid(length, width, height)
    elif volumeType == attachmentVolumeSphere:
        radius = attachmentPoint.volumeSize0
        untransformedPositions, faces = createMeshDataForSphere(radius)
    elif volumeType == attachmentVolumeCapsule:
        radius = attachmentPoint.volumeSize0
        height = attachmentPoint.volumeSize1
        untransformedPositions, faces = createMeshDataForCapsule(radius, height)
    else:
        # TODO create proper meshes for the 2 unknown shape types:
        print("Warning: The attachment volume %s has the unsupported type id %s" % (attachmentPoint.name, volumeType))
        untransformedPositions, faces = ([(0, 0, 0), (0, 0, 1), (0, 1, 1)], [(0, 1, 2)])

    boneName = boneNameForAttachmentPoint(attachmentPoint)
    meshName = boneName + 'Mesh'
    updateBoneShape(bone, poseBone, meshName, untransformedPositions, faces)


def updateBoneShapeOfLight(light, bone, poseBone):
    lightType = light.lightType
    if lightType == lightTypePoint:
        radius = light.attenuationFar
        untransformedPositions, faces = createMeshDataForSphere(radius)
    elif lightType == lightTypeSpot:
        radius = light.falloff
        height = light.attenuationFar
        untransformedPositions, faces = createMeshDataForLightCone(radius, height)
    else:
        raise Exception("Unsupported light type")

    boneName = boneNameForLight(light)
    meshName = boneName + 'Mesh'
    updateBoneShape(bone, poseBone, meshName, untransformedPositions, faces)


def updateBoneShapeOfWarp(warp, bone, poseBone):
    radius = warp.radius
    untransformedPositions, faces = createMeshDataForSphere(radius)

    boneName = boneNameForWarp(warp)
    meshName = boneName + 'Mesh'
    updateBoneShape(bone, poseBone, meshName, untransformedPositions, faces)


def updateBoneShapeOfForce(force, bone, poseBone):

    if force.shape == forceShapeSphere:
        untransformedPositions, faces = createMeshDataForSphere(force.width)
    elif force.shape == forceShapeCylinder:
        untransformedPositions, faces = createMeshDataForCylinder(force.width, force.height * 2)
    elif force.shape == forceShapeBox:
        untransformedPositions, faces = createMeshDataForCuboid(force.length, force.width, force.height * 2)
    elif force.shape == forceShapeHemisphere:
        untransformedPositions, faces = createMeshDataForHemisphere(force.width)
    elif force.shape == forceShapeConeDome:
        untransformedPositions, faces = createMeshDataForConeDome(force.width, force.height)
    else:
        untransformedPositions, faces = createMeshDataForSphere(force.width)
    boneName = force.boneName
    meshName = boneName + 'Mesh'
    updateBoneShape(bone, poseBone, meshName, untransformedPositions, faces)


def getRigidBodyBones(scene, rigidBodyBone):
    bone, armature = findBoneWithArmatureObject(scene, rigidBodyBone)
    if armature is None or bone is None:
        print("Warning: Could not find bone name specified in rigid body: %s" % rigidBodyBone)
        return None, None

    poseBone = armature.pose.bones[rigidBodyBone]
    if poseBone is None:
        print("Warning: Could not find posed bone: %s" % rigidBodyBone)
        return None, None

    return bone, poseBone


def createPhysicsShapeMeshData(shape):
    if shape.shape == "0":
        vertices, faces = createMeshDataForCuboid(2 * shape.size0, 2 * shape.size1, 2 * shape.size2)
    elif shape.shape == "1":
        vertices, faces = createMeshDataForSphere(shape.size0)
    elif shape.shape == "2":
        vertices, faces = createMeshDataForCapsule(shape.size0, shape.size1)
    elif shape.shape == "3":
        vertices, faces = createMeshDataForCylinder(shape.size0, shape.size1)
    else:
        meshObject = bpy.data.objects[shape.meshObjectName]
        mesh = meshObject.data

        vertices = [v.co for v in mesh.vertices]
        faces = [f.vertices for f in mesh.polygons]

    matrix = composeMatrix(shape.offset, shape.rotationEuler, shape.scale)
    vertices = [matrix @ mathutils.Vector(v) for v in vertices]

    return vertices, faces


def updateBoneShapeOfRigidBody(scene, rigidBody, rigidBodyBone):
    bone, poseBone = getRigidBodyBones(scene, rigidBodyBone)
    if bone is None or poseBone is None:
        return

    if len(rigidBody.physicsShapes) == 0:
        removeRigidBodyBoneShape(scene, rigidBodyBone)
        return

    combinedVertices, combinedFaces = [], []
    for shape in rigidBody.physicsShapes:
        vertices, faces = createPhysicsShapeMeshData(shape)
        # TODO: remove this check when mesh / convex hull is implemented
        if vertices is None or faces is None:
            continue

        faces = [[fe + len(combinedVertices) for fe in f] for f in faces]

        combinedVertices.extend(vertices)
        combinedFaces.extend(faces)

    updateBoneShape(bone, poseBone, "PhysicsShapeBoneMesh", combinedVertices, combinedFaces)


def removeRigidBodyBoneShape(scene, rigidBodyBone):
    bone, poseBone = getRigidBodyBones(scene, rigidBodyBone)
    if bone is None or poseBone is None:
        return

    poseBone.custom_shape = None
    bone.show_wire = False


def updateBoneShape(bone, poseBone, meshName, untransformedPositions, faces, matrix=mathutils.Matrix()):
    # Undo the rotation fix:
    matrix = rotFixMatrixInverted @ matrix
    boneScale = (bone.head - bone.tail).length
    invertedBoneScale = 1.0 / boneScale
    scaleMatrix = mathutils.Matrix()
    scaleMatrix[0][0] = invertedBoneScale
    scaleMatrix[1][1] = invertedBoneScale
    scaleMatrix[2][2] = invertedBoneScale
    matrix = scaleMatrix @ matrix

    # TODO reuse existing mesh of bone if it exists
    poseBone.custom_shape = createHiddenMeshObject(meshName, untransformedPositions, faces, matrix)
    bone.show_wire = True


def createAttachmentPointSymbolMesh():
    xd = 0.05
    yd = 0.025
    zd = 0.1
    vertices = [(-xd, 0, 0), (xd, 0, 0), (0, -yd, 0), (0, 0, zd)]
    faces = [(0, 1, 2), (0, 1, 3), (1, 2, 3), (0, 2, 3)]
    return vertices, faces


def createMeshDataForLightCone(radius, height, numberOfSideFaces=10):
    vertices = []
    faces = []
    for i in range(numberOfSideFaces):
        angle0 = 2 * math.pi * i / float(numberOfSideFaces)
        x = math.cos(angle0) * radius
        y = math.sin(angle0) * radius
        vertices.append((x, y, -height))

    tipVertexIndex = len(vertices)
    vertices.append((0, 0, 0))
    for i in range(numberOfSideFaces):
        nextI = ((i + 1) % numberOfSideFaces)
        i0 = nextI
        i1 = tipVertexIndex
        i2 = i
        faces.append((i0, i1, i2))
    return (vertices, faces)


def createMeshDataForSphere(radius, numberOfSideFaces=10, numberOfCircles=10):
    """returns vertices and faces"""
    vertices = []
    faces = []
    for circleIndex in range(numberOfCircles):
        circleAngle = math.pi * (circleIndex + 1) / float(numberOfCircles + 1)
        circleRadius = radius * math.sin(circleAngle)
        circleHeight = -radius * math.cos(circleAngle)
        nextCircleIndex = (circleIndex + 1) % numberOfCircles
        for i in range(numberOfSideFaces):
            angle = 2 * math.pi * i / float(numberOfSideFaces)
            nextI = ((i + 1) % numberOfSideFaces)
            if nextCircleIndex != 0:
                i0 = circleIndex * numberOfSideFaces + i
                i1 = circleIndex * numberOfSideFaces + nextI
                i2 = nextCircleIndex * numberOfSideFaces + nextI
                i3 = nextCircleIndex * numberOfSideFaces + i
                faces.append((i0, i1, i2, i3))
            x = math.cos(angle) * circleRadius
            y = math.sin(angle) * circleRadius
            vertices.append((x, y, circleHeight))

    bottomVertexIndex = len(vertices)
    vertices.append((0, 0, -radius))
    for i in range(numberOfSideFaces):
        nextI = ((i + 1) % numberOfSideFaces)
        i0 = i
        i1 = bottomVertexIndex
        i2 = nextI
        faces.append((i0, i1, i2))

    topVertexIndex = len(vertices)
    vertices.append((0, 0, radius))
    for i in range(numberOfSideFaces):
        nextI = ((i + 1) % numberOfSideFaces)
        i0 = ((numberOfCircles - 1) * numberOfSideFaces) + nextI
        i1 = topVertexIndex
        i2 = ((numberOfCircles - 1) * numberOfSideFaces) + i
        faces.append((i0, i1, i2))
    return (vertices, faces)


def createMeshDataForCuboid(sizeX, sizeY, sizeZ):
    """returns vertices and faces"""
    s0 = sizeX / 2.0
    s1 = sizeY / 2.0
    s2 = sizeZ / 2.0
    faces = []
    faces.append((0, 1, 3, 2))
    faces.append((6, 7, 5, 4))
    faces.append((4, 5, 1, 0))
    faces.append((2, 3, 7, 6))
    faces.append((0, 2, 6, 4))
    faces.append((5, 7, 3, 1))
    vertices = [(-s0, -s1, -s2), (-s0, -s1, s2), (-s0, s1, -s2), (-s0, s1, s2), (s0, -s1, -s2), (s0, -s1, s2), (s0, s1, -s2), (s0, s1, s2)]
    return (vertices, faces)


def createMeshDataForCapsule(radius, height, numberOfSideFaces=12, numberOfCircles=10):
    """returns vertices and faces"""
    vertices = []
    faces = []
    halfHeight = height / 2.0
    for circleIndex in range(numberOfCircles):
        if circleIndex < numberOfCircles / 2:
            circleAngle = math.pi * (circleIndex + 1) / float(numberOfCircles)
            circleHeight = -halfHeight - radius * math.cos(circleAngle)
        else:
            circleAngle = math.pi * (circleIndex) / float(numberOfCircles)
            circleHeight = halfHeight - radius * math.cos(circleAngle)
        circleRadius = radius * math.sin(circleAngle)
        nextCircleIndex = (circleIndex + 1) % numberOfCircles
        for i in range(numberOfSideFaces):
            angle = 2 * math.pi * i / float(numberOfSideFaces)
            nextI = ((i + 1) % numberOfSideFaces)
            if nextCircleIndex != 0:
                i0 = circleIndex * numberOfSideFaces + i
                i1 = circleIndex * numberOfSideFaces + nextI
                i2 = nextCircleIndex * numberOfSideFaces + nextI
                i3 = nextCircleIndex * numberOfSideFaces + i
                faces.append((i0, i1, i2, i3))
            x = math.cos(angle) * circleRadius
            y = math.sin(angle) * circleRadius
            vertices.append((x, y, circleHeight))

    bottomVertexIndex = len(vertices)
    vertices.append((0, 0, -halfHeight - radius))
    for i in range(numberOfSideFaces):
        nextI = ((i + 1) % numberOfSideFaces)
        i0 = i
        i1 = bottomVertexIndex
        i2 = nextI
        faces.append((i0, i1, i2))

    topVertexIndex = len(vertices)
    vertices.append((0, 0, halfHeight + radius))
    for i in range(numberOfSideFaces):
        nextI = ((i + 1) % numberOfSideFaces)
        i0 = ((numberOfCircles - 1) * numberOfSideFaces) + nextI
        i1 = topVertexIndex
        i2 = ((numberOfCircles - 1) * numberOfSideFaces) + i
        faces.append((i0, i1, i2))
    return (vertices, faces)


def createMeshDataForCylinder(radius, height, numberOfSideFaces=12):
    """returns the vertices and faces for a cylinder without head and bottom plane"""
    halfHeight = height / 2.0
    vertices = []
    faces = []
    for i in range(numberOfSideFaces):
        angle0 = 2 * math.pi * i / float(numberOfSideFaces)
        i0 = i * 2 + 1
        i1 = i * 2
        i2 = ((i + 1) * 2) % (numberOfSideFaces * 2)
        i3 = ((i + 1) * 2 + 1) % (numberOfSideFaces * 2)
        faces.append((i0, i1, i2, i3))
        x = math.cos(angle0) * radius
        y = math.sin(angle0) * radius
        vertices.append((x, y, -halfHeight))
        vertices.append((x, y, halfHeight))
    return (vertices, faces)


def createMeshDataForHemisphere(radius, numberOfSideFaces=12, numberOfCircles=5):
    """returns vertices and faces"""
    vertices = []
    faces = []
    semiCircles = numberOfCircles * 2
    for circleIndex in range(semiCircles):
        circleAngle = math.pi * (circleIndex) / float(semiCircles)
        circleRadius = radius * math.sin(circleAngle)
        circleHeight = radius * math.cos(circleAngle)
        nextCircleIndex = (circleIndex + 1) % semiCircles

        for i in range(numberOfSideFaces):
            angle = 2 * math.pi * i / float(numberOfSideFaces)
            nextI = ((i + 1) % numberOfSideFaces)
            if nextCircleIndex != 0:
                i0 = circleIndex * numberOfSideFaces + i
                i1 = circleIndex * numberOfSideFaces + nextI
                if nextCircleIndex < numberOfCircles + 1:
                    i2 = nextCircleIndex * numberOfSideFaces + nextI
                    i3 = nextCircleIndex * numberOfSideFaces + i
                    faces.append((i0, i1, i2, i3))
            x = math.cos(angle) * circleRadius
            y = math.sin(angle) * circleRadius
            vertices.append((x, y, circleHeight))

        if circleIndex == numberOfCircles:
            break

    bottomFace = []
    for i in range(numberOfSideFaces):
        bottomFace.append((numberOfCircles) * numberOfSideFaces + i)

    faces.append(bottomFace)

    return (vertices, faces)


def createMeshDataForConeDome(radius, coneRatio, numberOfSideFaces=12, numberOfCircles=3):
    """returns vertices and faces"""

    # TODO The formula for generating this mesh shape is a not a perfect match to the shape in-game.
    # TODO It could possibly be rewritten to match better.

    vertices = []
    faces = []
    semiCircles = numberOfCircles * 2
    coneRatio = sorted((0, coneRatio, 1))[1]
    cone = abs(coneRatio - 1)

    for circleIndex in range(semiCircles):
        circleAngle = math.pi * (circleIndex) / float(semiCircles)
        circleRadius = radius * math.sin(circleAngle) * cone * (coneRatio * 1.75 + cone)
        circleHeight = radius * math.cos(circleAngle) * cone + (coneRatio * radius)
        nextCircleIndex = (circleIndex + 1) % semiCircles

        for i in range(numberOfSideFaces):
            angle = 2 * math.pi * i / float(numberOfSideFaces)
            nextI = ((i + 1) % numberOfSideFaces)
            if nextCircleIndex != 0:
                i0 = circleIndex * numberOfSideFaces + i
                i1 = circleIndex * numberOfSideFaces + nextI
                if nextCircleIndex < numberOfCircles + 1:
                    i2 = nextCircleIndex * numberOfSideFaces + nextI
                    i3 = nextCircleIndex * numberOfSideFaces + i
                    faces.append((i0, i1, i2, i3))
            x = math.cos(angle) * circleRadius
            y = math.sin(angle) * circleRadius
            vertices.append((x, y, circleHeight))

        if circleIndex == numberOfCircles:
            break

    topVertexIndex = len(vertices)
    vertices.append((0, 0, 0))
    for i in range(numberOfSideFaces):
        nextI = ((i + 1) % numberOfSideFaces)
        i0 = ((numberOfCircles) * numberOfSideFaces) + nextI
        i1 = topVertexIndex
        i2 = ((numberOfCircles) * numberOfSideFaces) + i
        faces.append((i0, i1, i2))

    return (vertices, faces)


def typeIdOfObject(obj):
    objectType = type(obj)
    if objectType == bpy.types.Scene:
        return "SCENE"
    elif objectType == bpy.types.Object:
        return "OBJECT"
    else:
        raise Exception("Can't determine type id for type %s yet" % objectType)


def getOrCreateDefaultActionFor(ob):
    if ob.animation_data is not None:
        ob.animation_data_create()

    actionName = "DEFAULTS_FOR_" + ob.name
    action = bpy.data.actions[actionName] if actionName in bpy.data.actions else bpy.data.actions.new(actionName)
    action.use_fake_user = True
    action.id_root = typeIdOfObject(ob)

    return action


def transferSpawnPoint(transferer):
    transferer.transferAnimatableVector3("location")


def transferParticleSystem(transferer):
    transferer.transferAnimatableFloat("emissionSpeed1")
    transferer.transferAnimatableFloat("emissionSpeed2")
    transferer.transferBoolean("randomizeWithEmissionSpeed2", tillVersion=12)
    transferer.transferBit("additionalFlags", "randomizeWithEmissionSpeed2", sinceVersion=13)
    transferer.transferAnimatableFloat("emissionAngleX")
    transferer.transferAnimatableFloat("emissionAngleY")
    transferer.transferAnimatableFloat("emissionSpreadX")
    transferer.transferAnimatableFloat("emissionSpreadY")
    transferer.transferAnimatableFloat("lifespan1")
    transferer.transferAnimatableFloat("lifespan2")
    transferer.transferBoolean("randomizeWithLifespan2", tillVersion=12)
    transferer.transferBit("additionalFlags", "randomizeWithLifespan2", sinceVersion=13)
    transferer.transferFloat("killSphere")
    transferer.transferFloat("zAcceleration")
    transferer.transferFloat("sizeAnimationMiddle")
    transferer.transferFloat("colorAnimationMiddle")
    transferer.transferFloat("alphaAnimationMiddle")
    transferer.transferFloat("rotationAnimationMiddle")
    transferer.transferFloat("sizeHoldTime", sinceVersion=17)
    transferer.transferFloat("colorHoldTime", sinceVersion=17)
    transferer.transferFloat("alphaHoldTime", sinceVersion=17)
    transferer.transferFloat("rotationHoldTime", sinceVersion=17)
    transferer.transferEnum("sizeSmoothingType", sinceVersion=17)
    transferer.transferEnum("colorSmoothingType", sinceVersion=17)
    transferer.transferEnum("rotationSmoothingType", sinceVersion=17)
    # the following 6 values get set based on smoothing types:
    # transferer.transferBit("flags", "smoothRotation")
    # transferer.transferBit("flags", "bezSmoothRotation")
    # transferer.transferBit("flags", "smoothSize")
    # transferer.transferBit("flags", "bezSmoothSize")
    # transferer.transferBit("flags", "smoothColor")
    # transferer.transferBit("flags", "bezSmoothColor")
    transferer.transferAnimatableVector3("particleSizes1")
    transferer.transferAnimatableVector3("rotationValues1")
    transferer.transferAnimatableColor("initialColor1")
    transferer.transferAnimatableColor("middleColor1")
    transferer.transferAnimatableColor("finalColor1")
    transferer.transferFloat("drag")
    transferer.transferFloat("mass")
    transferer.transferFloat("mass2")
    transferer.transferBit("additionalFlags", "randomizeWithMass2", sinceVersion=21)
    transferer.transferFloat("unknownFloat2c")
    transferer.transferBoolean("trailingEnabled", tillVersion=12)
    transferer.transferBit("additionalFlags", "trailingEnabled", sinceVersion=13)
    transferer.transferInt("maxParticles")
    transferer.transferAnimatableFloat("emissionRate")
    transferer.transferEnum("emissionAreaType")
    transferer.transferAnimatableVector3("emissionAreaSize")
    transferer.transferAnimatableVector3("emissionAreaCutoutSize")
    transferer.transferAnimatableFloat("emissionAreaRadius")
    transferer.transferAnimatableFloat("emissionAreaCutoutRadius")
    transferer.transferEnum("emissionType")
    transferer.transferBoolean("randomizeWithParticleSizes2")
    transferer.transferAnimatableVector3("particleSizes2")
    transferer.transferBoolean("randomizeWithRotationValues2")
    transferer.transferAnimatableVector3("rotationValues2")
    transferer.transferBoolean("randomizeWithColor2")
    transferer.transferAnimatableColor("initialColor2")
    transferer.transferAnimatableColor("middleColor2")
    transferer.transferAnimatableColor("finalColor2")
    transferer.transferAnimatableInt16("partEmit")
    transferer.transferInt("phase1StartImageIndex")
    transferer.transferInt("phase1EndImageIndex")
    transferer.transferInt("phase2StartImageIndex")
    transferer.transferInt("phase2EndImageIndex")
    transferer.transferFloat("relativePhase1Length")
    transferer.transferInt("numberOfColumns")
    transferer.transferInt("numberOfRows")
    transferer.transferFloat("columnWidth")
    transferer.transferFloat("rowHeight")
    transferer.transferFloat("bounce")
    transferer.transferFloat("friction")
    transferer.transferEnum("particleType")
    transferer.transferFloat("lengthWidthRatio")
    transferer.transfer16Bits("localForceChannels")
    transferer.transfer16Bits("worldForceChannels")
    transferer.transferFloat("trailingParticlesChance")
    transferer.transferAnimatableFloat("trailingParticlesRate")
    transferer.transferFloat("noiseAmplitude")
    transferer.transferFloat("noiseFrequency")
    transferer.transferFloat("noiseCohesion")
    transferer.transferFloat("noiseEdge")
    transferer.transferBit("flags", "sort")
    transferer.transferBit("flags", "collideTerrain")
    transferer.transferBit("flags", "collideObjects")
    transferer.transferBit("flags", "spawnOnBounce")
    transferer.transferBit("flags", "cutoutEmissionArea")
    transferer.transferBit("flags", "inheritEmissionParams")
    transferer.transferBit("flags", "inheritParentVel")
    transferer.transferBit("flags", "sortByZHeight")
    transferer.transferBit("flags", "reverseIteration")
    transferer.transferBit("flags", "litParts")
    transferer.transferBit("flags", "randFlipBookStart")
    transferer.transferBit("flags", "multiplyByGravity")
    transferer.transferBit("flags", "clampTailParts")
    transferer.transferBit("flags", "spawnTrailingParts")
    transferer.transferBit("flags", "useVertexAlpha")
    transferer.transferBit("flags", "modelParts")
    transferer.transferBit("flags", "swapYZonModelParts")
    transferer.transferBit("flags", "scaleTimeByParent")
    transferer.transferBit("flags", "useLocalTime")
    transferer.transferBit("flags", "simulateOnInit")
    transferer.transferBit("flags", "copy")
    transferer.transferFloat("windMultiplier")
    transferer.transferEnum("lodReduce")
    transferer.transferEnum("lodCut")


def transferParticleSystemCopy(transferer):
    transferer.transferAnimatableFloat("emissionRate")
    transferer.transferAnimatableInt16("partEmit")


def transferRibbon(transferer):
    transferer.transferBit("additionalFlags", "worldSpace", sinceVersion=8)
    transferer.transferAnimatableFloat("speed")
    transferer.transferAnimatableFloat("yaw")
    transferer.transferAnimatableFloat("pitch")
    transferer.transferAnimatableFloat("lifespan")
    transferer.transferFloat("gravity")
    transferer.transferFloat("sizeMiddleTime")
    transferer.transferFloat("colorMiddleTime")
    transferer.transferFloat("alphaMiddleTime")
    transferer.transferFloat("rotationMiddleTime")
    transferer.transferFloat("sizeMiddleHoldTime", sinceVersion=8)
    transferer.transferFloat("colorMiddleHoldTime", sinceVersion=8)
    transferer.transferFloat("alphaMiddleHoldTime", sinceVersion=8)
    transferer.transferFloat("rotationMiddleHoldTime", sinceVersion=8)
    transferer.transferAnimatableVector3("size")
    transferer.transferAnimatableVector3("rotation")
    transferer.transferAnimatableColor("baseColoring")
    transferer.transferAnimatableColor("centerColoring")
    transferer.transferAnimatableColor("tipColoring")
    transferer.transferFloat("drag")
    transferer.transferFloat("mass")
    transferer.transferBoolean("worldSpace", tillVersion=6)
    transferer.transfer16Bits("localForceChannels")
    transferer.transfer16Bits("worldForceChannels")
    transferer.transferFloat("surfaceNoiseAmplitude")
    transferer.transferFloat("surfaceNoiseNumberOfWaves")
    transferer.transferFloat("surfaceNoiseFrequency")
    transferer.transferFloat("surfaceNoiseScale")
    transferer.transferEnum("ribbonType")
    transferer.transferEnum("cullType")
    transferer.transferFloat("ribbonDivisions")
    transferer.transferInt("ribbonSides")
    transferer.transferFloat("starRatio")
    transferer.transferAnimatableFloat("length")
    transferer.transferAnimatableUInt32("active")
    transferer.transferBit("flags", "collideWithTerrain")
    transferer.transferBit("flags", "collideWithObjects")
    transferer.transferBit("flags", "edgeFalloff")
    transferer.transferBit("flags", "inheritParentVelocity")
    transferer.transferBit("flags", "smoothSize")
    transferer.transferBit("flags", "bezierSmoothSize")
    transferer.transferBit("flags", "useVertexAlpha")
    transferer.transferBit("flags", "scaleTimeByParent")
    transferer.transferBit("flags", "forceCPUSimulation")
    transferer.transferBit("flags", "useLocaleTime")
    transferer.transferBit("flags", "simulateOnInitialization")
    transferer.transferBit("flags", "useLengthAndTime")
    transferer.transferBit("flags", "accurateGPUTangents")
    transferer.transferEnum("sizeSmoothing")
    transferer.transferEnum("colorSmoothing")
    transferer.transferFloat("friction", sinceVersion=8)
    transferer.transferFloat("bounce", sinceVersion=8)
    transferer.transferEnum("lodReduce")
    transferer.transferEnum("lodCut")
    transferer.transferEnum("yawVariationType")
    transferer.transferAnimatableFloat("yawVariationAmplitude")
    transferer.transferAnimatableFloat("yawVariationFrequency")
    transferer.transferEnum("pitchVariationType")
    transferer.transferAnimatableFloat("pitchVariationAmplitude")
    transferer.transferAnimatableFloat("pitchVariationFrequency")
    transferer.transferEnum("speedVariationType")
    transferer.transferAnimatableFloat("speedVariationAmplitude")
    transferer.transferAnimatableFloat("speedVariationFrequency")
    transferer.transferEnum("sizeVariationType")
    transferer.transferAnimatableFloat("sizeVariationAmplitude")
    transferer.transferAnimatableFloat("sizeVariationFrequency")
    transferer.transferEnum("alphaVariationType")
    transferer.transferAnimatableFloat("alphaVariationAmplitude")
    transferer.transferAnimatableFloat("alphaVariationFrequency")
    transferer.transferAnimatableFloat("parentVelocity")
    transferer.transferAnimatableFloat("overlayPhase")


def transferRibbonEndPoint(transferer):
    transferer.transferFloat("tangent1")
    transferer.transferFloat("tangent2")
    transferer.transferFloat("tangent3")
    transferer.transferAnimatableFloat("yaw")
    transferer.transferEnum("yawVariationType")
    transferer.transferAnimatableFloat("yawVariationAmplitude")
    transferer.transferAnimatableFloat("yawVariationFrequency")
    transferer.transferAnimatableFloat("pitch")
    transferer.transferEnum("pitchVariationType")
    transferer.transferAnimatableFloat("pitchVariationAmplitude")
    transferer.transferAnimatableFloat("pitchVariationFrequency")
    transferer.transferAnimatableFloat("length")
    transferer.transferEnum("speedVariationType")
    transferer.transferAnimatableFloat("speedVariationAmplitude")
    transferer.transferAnimatableFloat("speedVariationFrequency")


def transferProjection(transferer):
    transferer.transferEnum("projectionType")
    transferer.transferAnimatableFloat("fieldOfView")
    transferer.transferAnimatableFloat("aspectRatio")
    transferer.transferAnimatableFloat("near")
    transferer.transferAnimatableFloat("far")
    transferer.transferFloat("alphaOverTimeStart")
    transferer.transferFloat("alphaOverTimeMid")
    transferer.transferFloat("alphaOverTimeEnd")
    transferer.transferFloat("splatLifeTimeAttack")
    transferer.transferFloat("splatLifeTimeAttackTo")
    transferer.transferFloat("splatLifeTimeHold")
    transferer.transferFloat("splatLifeTimeHoldTo")
    transferer.transferFloat("splatLifeTimeDecay")
    transferer.transferFloat("splatLifeTimeDecayTo")
    transferer.transferFloat("attenuationPlaneDistance")
    transferer.transferAnimatableUInt32("active")
    transferer.transferEnum("splatLayer")
    transferer.transferEnum("lodReduce")
    transferer.transferEnum("lodCut")
    transferer.transferMultipleBits("flags")


def transferWarp(transferer):
    transferer.transferAnimatableFloat("radius")
    transferer.transferAnimatableFloat("unknown9306aac0")
    transferer.transferAnimatableFloat("compressionStrength")
    transferer.transferAnimatableFloat("unknown50c7f2b4")
    transferer.transferAnimatableFloat("unknown8d9c977c")
    transferer.transferAnimatableFloat("unknownca6025a2")


def transferForce(transferer):
    transferer.transferEnum("type")
    transferer.transferEnum("shape")
    transferer.transfer32Bits("channels")
    transferer.transferAnimatableFloat("strength")
    transferer.transferAnimatableFloat("width")
    transferer.transferAnimatableFloat("height")
    transferer.transferAnimatableFloat("length")
    transferer.transferBit("flags", "useFalloff")
    transferer.transferBit("flags", "useHeightGradient")
    transferer.transferBit("flags", "unbounded")


def transferRigidBody(transferer):
    transferer.transferFloat("unknownAt0", tillVersion=2)
    transferer.transferFloat("unknownAt4", tillVersion=2)
    transferer.transferFloat("unknownAt8", tillVersion=2)
    # skip other unknown values for now
    transferer.transferInt("simulationType", sinceVersion=3)
    transferer.transferInt("physicalMaterial", sinceVersion=3)
    transferer.transferFloat("density", sinceVersion=3)
    transferer.transferFloat("friction", sinceVersion=3)
    transferer.transferFloat("restitution", sinceVersion=3)
    transferer.transferFloat("linearDamp", sinceVersion=3)
    transferer.transferFloat("angularDamp", sinceVersion=3)
    transferer.transferFloat("gravityScale", sinceVersion=3)
    transferer.transferBit("flags", "collidable")
    transferer.transferBit("flags", "walkable")
    transferer.transferBit("flags", "stackable")
    transferer.transferBit("flags", "simulateOnCollision")
    transferer.transferBit("flags", "ignoreLocalBodies")
    transferer.transferBit("flags", "alwaysExists")
    transferer.transferBit("flags", "doNotSimulate")
    transferer.transfer16Bits("localForces")
    transferer.transferBit("worldForces", "wind")
    transferer.transferBit("worldForces", "explosion")
    transferer.transferBit("worldForces", "energy")
    transferer.transferBit("worldForces", "blood")
    transferer.transferBit("worldForces", "magnetic")
    transferer.transferBit("worldForces", "grass")
    transferer.transferBit("worldForces", "brush")
    transferer.transferBit("worldForces", "trees")
    transferer.transferInt("priority")


def transferPhysicsShape(transferer):
    transferer.transferEnum("shape")
    # skip unknown values for now
    transferer.transferFloat("size0")
    transferer.transferFloat("size1")
    transferer.transferFloat("size2")


def transferStandardMaterial(transferer):
    transferer.transferMultipleBits("flags", [
        "useVertexColor",
        "useVertexAlpha",
        "unfogged",
        "twoSided",
        "unshaded",
        "noShadowsCast",
        "noHitTest",
        "noShadowsReceived",
        "depthPrepass",
        "useTerrainHDR",
        "unknown0x400",
        "simulateRoughness",
        "perPixelForwardLighting",
        "depthFog",
        "transparentShadows",
        "decalLighting",
        "transparencyDepthEffects",
        "transparencyLocalLights",
        "disableSoft",
        "darkNormalMapping",
        "hairLayerSorting",
        "acceptSplats",
        "decalRequiredOnLowEnd",
        "emissiveRequiredOnLowEnd",
        "specularRequiredOnLowEnd",
        "acceptSplatsOnly",
        "backgroundObject",
        "unknown0x8000000",
        "zpFillRequiredOnLowEnd",
        "excludeFromHighlighting",
        "clampOutput",
    ])
    transferer.transferBit("flags", "geometryVisible", sinceVersion=17)

    # depthBlendFalloff needs to be transfered before useDepthBlendFalloff:
    # That way a corrupted model with useDepthBlendFalloff=true
    # but depthBlendFalloff==0.0 will be fixed:
    # When the flag gets set in the blender material it sets
    # the depthBlendFalloff to 0.2 and thus fixes the combination
    transferer.transferFloat("depthBlendFalloff")
    transferer.transferBit("additionalFlags", "useDepthBlendFalloff")
    transferer.transferBit("additionalFlags", "unknownFlag0x200")
    transferer.transferEnum("blendMode")
    transferer.transferInt("priority")
    transferer.transferFloat("specularity")
    transferer.transferInt("cutoutThresh")
    transferer.transferFloat("specMult")
    transferer.transferFloat("emisMult")
    transferer.transferFloat("envConstMult", sinceVersion=20)
    transferer.transferFloat("envDiffMult", sinceVersion=20)
    transferer.transferFloat("envSpecMult", sinceVersion=20)
    transferer.transferEnum("layerBlendType")
    transferer.transferEnum("emisBlendType")
    transferer.transferEnum("emisMode")
    transferer.transferEnum("specType")
    transferer.transferAnimatableFloat("parallaxHeight")


def transferDisplacementMaterial(transferer):
    transferer.transferAnimatableFloat("strengthFactor")
    transferer.transferInt("priority")


def transferCompositeMaterial(transferer):
    pass


def transferCompositeMaterialSection(transferer):
    transferer.transferAnimatableFloat("alphaFactor")


def transferTerrainMaterial(transferer):
    pass


def transferVolumeMaterial(transferer):
    transferer.transferAnimatableFloat("volumeDensity")


def transferVolumeNoiseMaterial(transferer):
    transferer.transferAnimatableFloat("volumeDensity")
    transferer.transferAnimatableFloat("nearPlane")
    transferer.transferAnimatableFloat("falloff")
    transferer.transferAnimatableVector3("scrollRate")
    transferer.transferAnimatableVector3("translation")
    transferer.transferAnimatableVector3("scale")
    transferer.transferAnimatableVector3("rotation")
    transferer.transferInt("alphaTreshhold")
    transferer.transferBit("flags", "drawAfterTransparency")


def transferCreepMaterial(transferer):
    pass


def transfersplatTerrainBakeMaterial(transferer):
    pass


def transferLensFlareMaterial(transferer):
    pass


def transferMaterialLayer(transferer):
    transferer.transferString("imagePath")
    transferer.transferInt("unknownbd3f7b5d")
    transferer.transferAnimatableColor("color")
    transferer.transferBit("flags", "textureWrapX")
    transferer.transferBit("flags", "textureWrapY")
    transferer.transferBit("flags", "invertColor")
    transferer.transferBit("flags", "clampColor")
    transferer.transferBitEnum("flags", "colorEnabled")
    transferer.transferEnum("uvSource")
    transferer.transferEnum("colorChannelSetting")
    transferer.transferAnimatableFloat("brightMult")
    transferer.transferAnimatableFloat("midtoneOffset")
    transferer.transferAnimatableVector2("uvOffset")
    transferer.transferAnimatableVector3("uvAngle")
    transferer.transferAnimatableVector2("uvTiling")
    transferer.transferAnimatableVector3("triPlanarOffset", sinceVersion=24)
    transferer.transferAnimatableVector3("triPlanarScale", sinceVersion=24)

    transferer.transferInt("flipBookRows")
    transferer.transferInt("flipBookColumns")
    transferer.transferAnimatableUInt16("flipBookFrame")
    transferer.transferAnimatableFloat("brightness")
    transferer.transferEnum("rttChannel")
    transferer.transferEnum("fresnelType")
    transferer.transferFloat("fresnelExponent")
    transferer.transferFloat("fresnelMin")
    transferer.transferFloat("fresnelRotationYaw", sinceVersion=25)
    transferer.transferFloat("fresnelRotationPitch", sinceVersion=25)
    transferer.transferBit("flags", "fresnelLocalTransform", sinceVersion=25)
    transferer.transferBit("flags", "fresnelDoNotMirror", sinceVersion=25)

    transferer.transferInt("videoFrameRate")
    transferer.transferInt("videoStartFrame")
    transferer.transferInt("videoEndFrame")
    transferer.transferEnum("videoMode")
    transferer.transferBoolean("videoSyncTiming")
    transferer.transferAnimatableBooleanBasedOnSDU3("videoPlay")
    transferer.transferAnimatableBooleanBasedOnSDFG("videoRestart")


def transferAnimation(transferer):
    transferer.transferFloat("movementSpeed")
    transferer.transferInt("frequency")
    transferer.transferBit("flags", "notLooping")
    transferer.transferBit("flags", "alwaysGlobal")
    transferer.transferBit("flags", "globalInPreviewer")


def transferSTC(transferer):
    transferer.transferBoolean("runsConcurrent")
    transferer.transferInt("priority")


def transferCamera(transferer):
    transferer.transferAnimatableFloat("fieldOfView")
    transferer.transferAnimatableFloat("farClip")
    transferer.transferAnimatableFloat("nearClip")
    transferer.transferAnimatableFloat("clip2")
    transferer.transferAnimatableFloat("focalDepth")
    transferer.transferAnimatableFloat("falloffStart")
    transferer.transferAnimatableFloat("falloffEnd")
    transferer.transferAnimatableFloat("depthOfField")


def transferFuzzyHitTest(transferer):
    transferer.transferEnum("shape")
    transferer.transferFloat("size0")
    transferer.transferFloat("size1")
    transferer.transferFloat("size2")


def transferLight(transferer):
    transferer.transferEnum("lightType")
    transferer.transferAnimatableVector3("lightColor")
    transferer.transferBit("flags", "shadowCast")
    transferer.transferBit("flags", "specular")
    transferer.transferBit("flags", "affectedByAO")
    transferer.transferBit("flags", "lightOpaqueObjects")
    transferer.transferBit("flags", "lightTransparentObjects")
    transferer.transferBit("flags", "useTeamColor")
    transferer.transferEnum("lodCut")
    transferer.transferEnum("shadowLodCut")
    transferer.transferAnimatableFloat("lightIntensity")
    transferer.transferAnimatableVector3("specColor")
    transferer.transferAnimatableFloat("specIntensity")
    transferer.transferAnimatableFloat("attenuationFar")
    transferer.transferFloat("unknownAt148")
    transferer.transferAnimatableFloat("attenuationNear")
    transferer.transferAnimatableFloat("hotSpot")
    transferer.transferAnimatableFloat("falloff")


def transferBillboardBehavior(transferer):
    transferer.transferEnum("billboardType")


def transferIkChain(transferer):
    transferer.transferFloat("maxSearchUp")
    transferer.transferFloat("maxSearchDown")
    transferer.transferFloat("maxSpeed")
    transferer.transferFloat("goalPosThreshold")


def transferTurretBehaviorPart(transferer):
    transferer.transferBit("flags", "mainTurretBone")
    transferer.transferInt("groupId")
    transferer.transferBit("yawFlags", "yawLimited")
    transferer.transferFloat("yawMin")
    transferer.transferFloat("yawMax")
    transferer.transferFloat("yawWeight")
    transferer.transferBit("pitchFlags", "pitchLimited")
    transferer.transferFloat("pitchMin")
    transferer.transferFloat("pitchMax")
    transferer.transferFloat("pitchWeight")
    transferer.transferFloat("unknownAt132")
    transferer.transferFloat("unknownAt136")
    transferer.transferFloat("unknownAt140")
    transferer.transferFloat("unknownAt144")
    transferer.transferFloat("unknownAt148")


def transferPhysicsJoint(transferer):
    transferer.transferEnum("jointType")
    transferer.transferBoolean("limit")
    transferer.transferFloat("limitMin")
    transferer.transferFloat("limitMax")
    transferer.transferFloat("coneAngle")
    transferer.transferBoolean("friction")
    transferer.transferFloat("frictionAmount")
    transferer.transferFloat("dampingRatio")
    transferer.transferFloat("angularFrequency")
    transferer.transferInt("shapeCollisionValue")


def transferBufferMaterial(transferer):
    pass


m3MaterialFieldNames = {
    standardMaterialTypeIndex: "standardMaterials",
    displacementMaterialTypeIndex: "displacementMaterials",
    compositeMaterialTypeIndex: "compositeMaterials",
    terrainMaterialTypeIndex: "terrainMaterials",
    volumeMaterialTypeIndex: "volumeMaterials",
    creepMaterialTypeIndex: "creepMaterials",
    volumeNoiseMaterialTypeIndex: "volumeNoiseMaterials",
    stbMaterialTypeIndex: "splatTerrainBakeMaterials",
    # TODO: reflection material
    lensFlareMaterialTypeIndex: "lensFlareMaterial",
    bufferMaterialTypeIndex: "bufferMaterial",
}

materialTransferMethods = {
    standardMaterialTypeIndex: transferStandardMaterial,
    displacementMaterialTypeIndex: transferDisplacementMaterial,
    compositeMaterialTypeIndex: transferCompositeMaterial,
    terrainMaterialTypeIndex: transferTerrainMaterial,
    volumeMaterialTypeIndex: transferVolumeMaterial,
    creepMaterialTypeIndex: transferCreepMaterial,
    volumeNoiseMaterialTypeIndex: transferVolumeNoiseMaterial,
    stbMaterialTypeIndex: transfersplatTerrainBakeMaterial,
    # TODO: reflection material
    lensFlareMaterialTypeIndex: transferLensFlareMaterial,
    bufferMaterialTypeIndex: transferBufferMaterial,
}
