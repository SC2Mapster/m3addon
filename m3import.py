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

from timeit import timeit
from . import m3
from . import shared
from . import cm
import bpy
import mathutils
import math
import bmesh
from bpy_extras import io_utils
import bpy.types as bt
from os import path


def toBlenderQuaternion(m3Quaternion):
    return mathutils.Quaternion((m3Quaternion.w, m3Quaternion.x, m3Quaternion.y, m3Quaternion.z))


def toBlenderVector3(m3Vector3):
    return mathutils.Vector((m3Vector3.x, m3Vector3.y, m3Vector3.z))


def toBlenderVector2(m3Vector2):
    return mathutils.Vector((m3Vector2.x, m3Vector2.y))


def toBlenderColorVector(m3Color):
    return mathutils.Vector((m3Color.red / 255.0, m3Color.green / 255.0, m3Color.blue / 255.0, m3Color.alpha / 255.0))


def toBlenderUVCoordinate(m3UVCoordinate, uvwMult, uvwOffset):
    return (
        (m3UVCoordinate.x * (uvwMult / 16.0) / 2048.0) + uvwOffset,
        1 - ((m3UVCoordinate.y * (uvwMult / 16.0) / 2048.0) + uvwOffset)
    )


def toBlenderMatrix(m3Matrix):
    return mathutils.Matrix((
        (m3Matrix.x.x, m3Matrix.y.x, m3Matrix.z.x, m3Matrix.w.x),
        (m3Matrix.x.y, m3Matrix.y.y, m3Matrix.z.y, m3Matrix.w.y),
        (m3Matrix.x.z, m3Matrix.y.z, m3Matrix.z.z, m3Matrix.w.z),
        (m3Matrix.x.w, m3Matrix.y.w, m3Matrix.z.w, m3Matrix.w.w)
    ))


FRAME_RATE = 30


def msToFrame(timeInMS):
    return round(timeInMS / 1000.0 * FRAME_RATE)


def insertLinearKeyFrame(curve, frame, value):
    keyFrame = curve.keyframe_points.insert(frame, value)
    keyFrame.interpolation = "LINEAR"


def insertConstantKeyFrame(curve, frame, value):
    keyFrame = curve.keyframe_points.insert(frame, value)
    keyFrame.interpolation = "CONSTANT"


def frameValuePairs(timeValueMap):
    timeValues = list(timeValueMap.keys())
    timeValues.sort()
    for timeInMS in timeValues:
        frame = msToFrame(timeInMS)
        value = timeValueMap[timeInMS]
        yield(frame, value)


def extendTimeToValueMapByInterpolation(timeToVectorMap, wantedTimes, interpolationFunc):
    timesWithValues = list(timeToVectorMap.keys())
    timesWithValues.sort()
    wantedTimes = list(wantedTimes)
    wantedTimes.sort()

    wantedTimesIndex = 0
    leftInterpolationTime = timesWithValues[0]
    leftInterpolationValue = timeToVectorMap[leftInterpolationTime]
    while (wantedTimesIndex < len(wantedTimes)) and (wantedTimes[wantedTimesIndex] <= leftInterpolationTime):
        timeToVectorMap[wantedTimes[wantedTimesIndex]] = leftInterpolationValue
        wantedTimesIndex += 1

    if wantedTimesIndex == len(wantedTimes):
        return
    wantedTime = wantedTimes[wantedTimesIndex]

    for timeWithValue in timesWithValues[1:]:
        rightInterpolationTime = timeWithValue
        rightInterpolationValue = timeToVectorMap[rightInterpolationTime]
        while wantedTime <= rightInterpolationTime:
            if wantedTime == rightInterpolationTime:
                timeToVectorMap[wantedTime] = rightInterpolationValue
            else:
                timeSinceLeftTime = wantedTime - leftInterpolationTime
                intervalLength = rightInterpolationTime - leftInterpolationTime
                rightFactor = timeSinceLeftTime / intervalLength
                timeToVectorMap[wantedTime] = interpolationFunc(leftInterpolationValue, rightInterpolationValue, rightFactor)
            wantedTimesIndex += 1
            if wantedTimesIndex == len(wantedTimes):
                return
            wantedTime = wantedTimes[wantedTimesIndex]
        leftInterpolationTime = rightInterpolationTime
        leftInterpolationValue = rightInterpolationValue

    for wantedTime in wantedTimes[wantedTimesIndex:]:
        timeToVectorMap[wantedTime] = leftInterpolationValue


def extendTimeToVectorMapByInterpolation(timeToVectorMap, wantedTimes):
    return extendTimeToValueMapByInterpolation(timeToVectorMap, wantedTimes, shared.vectorInterpolationFunction)


def extendTimeToQuaternionMapByInterpolation(timeToVectorMap, wantedTimes):
    return extendTimeToValueMapByInterpolation(timeToVectorMap, wantedTimes, shared.quaternionInterpolationFunction)


def convertToBlenderVector3Map(timeToM3VectorMap):
    result = {}
    for key, m3Vector3 in timeToM3VectorMap.items():
        result[key] = toBlenderVector3(m3Vector3)
    return result


def convertToBlenderQuaternionMap(timeToM3VectorMap):
    result = {}
    for key, m3Quaternion in timeToM3VectorMap.items():
        result[key] = toBlenderQuaternion(m3Quaternion)
    return result


def visualizeMatrix(matrix, at3DCursor):
    mesh = bpy.data.meshes.new('AxisMesh')
    meshObject = bpy.data.objects.new('AxisMesh', mesh)
    if at3DCursor:
        meshObject.location = bpy.context.scene.cursor.location
    else:
        meshObject.location = (0, 0, 0)
    meshObject.show_name = True
    oVertex = matrix.translation
    matrix3x3 = matrix.to_3x3()
    xVertex = oVertex + matrix3x3.col[0]
    yVertex = oVertex + matrix3x3.col[1]
    zVertex = oVertex + matrix3x3.col[2]
    vertices = [oVertex, xVertex, yVertex, zVertex]
    edges = [(0, 1), (0, 2), (0, 3)]
    bpy.context.scene.collection.objects.link(meshObject)
    mesh.from_pydata(vertices, edges, [])
    mesh.update(calc_edges=True)


def checkOrder(boneEntries):
    index = 0
    for boneEntry in boneEntries:
        if boneEntry.parent != -1:
            if (boneEntry.parent >= index):
                raise Exception("Bones are not sorted as expected")
        index += 1


def determineTails(m3Bones, heads, boneDirectionVectors):
    childBoneIndexLists = []
    for boneIndex, boneEntry in enumerate(m3Bones):
        childBoneIndexLists.append([])
        if boneEntry.parent != -1:
            childBoneIndexLists[boneEntry.parent].append(boneIndex)

    tails = []
    for m3Bone, head, childIndices, boneDirectionVector in zip(m3Bones, heads, childBoneIndexLists, boneDirectionVectors):

        if False:
            if len(childIndices) == 1:
                tail = heads[childIndices[0]]
            elif len(childIndices) > 1:
                childDeltaSum = mathutils.Vector((0.0, 0.0, 0.0))
                for childIndex in childIndices:
                    headToChildHead = heads[childIndex] - head
                    childDeltaSum += headToChildHead
                childDeltaAvg = childDeltaSum / len(childIndices)
                tail = head + childDeltaAvg
            elif m3Bone.parent != -1:
                parentDelta = tails[m3Bone.parent] - heads[m3Bone.parent]
                tail = head + (parentDelta * 0.5)
            else:
                tail = head + mathutils.Vector((0.0, 0.1, 0.0))
        else:
            length = 0.1
            for childIndex in childIndices:
                headToChildHead = heads[childIndex] - head
                if headToChildHead.length >= 0.0001:
                    if abs(headToChildHead.angle(boneDirectionVector)) < 0.1:
                        length = headToChildHead.length
            tailOffset = length * boneDirectionVector
            tail = head + tailOffset
            # At extreme high tail/head values a higher offset needs to be chosen
            # since otherwise tail and head is the same due to rouding mistakes
            # If head and tail are the same then the bone will be removed after leaving edit mode
            # The length of tailOffset gets doubled each step in order to get in a reasonable amount of steps
            # to a value that matters
            while (tail - head).length == 0:
                tailOffset *= 2
                tail = head + tailOffset

        tails.append(tail)
    return tails


def determineRolls(absoluteBoneRestPositions, heads, tails):
    rolls = []
    for absBoneRestMatrix, head, tail in zip(absoluteBoneRestPositions, heads, tails):
        editBoneMatrix = boneMatrix(head=head, tail=tail, roll=0)
        boneMatrix3x3 = editBoneMatrix.to_3x3()

        angleZToZ = boneMatrix3x3.col[2].angle(absBoneRestMatrix.col[2].to_3d())
        angleZToX = boneMatrix3x3.col[2].angle(absBoneRestMatrix.col[0].to_3d())

        if angleZToX > math.pi / 2.0:
            rollAngle = angleZToZ
        else:
            rollAngle = -angleZToZ

        rolls.append(rollAngle)
    return rolls


def determineAbsoluteBoneRestPositions(model):
    matrices = []
    for inverseBoneRestPosition in model.absoluteInverseBoneRestPositions:
        matrix = toBlenderMatrix(inverseBoneRestPosition.matrix)
        matrix = matrix.inverted()
        matrix = matrix @ shared.rotFixMatrix
        matrices.append(matrix)
    return matrices


class M3ToBlenderDataTransferer:
    def __init__(self, importer, objectWithAnimationData, animPathPrefix, blenderObject, m3Object):
        self.importer = importer
        self.objectWithAnimationData = objectWithAnimationData
        self.animPathPrefix = animPathPrefix
        self.blenderObject = blenderObject
        self.m3Object = m3Object
        self.m3Version = m3Object.structureDescription.structureVersion

    def transferAnimatableFloat(self, fieldName):
        animationReference = getattr(self.m3Object, fieldName)
        setattr(self.blenderObject, fieldName, animationReference.initValue)
        animationHeader = animationReference.header
        animId = animationHeader.animId
        animPath = self.animPathPrefix + fieldName
        defaultValue = animationReference.initValue
        self.importer.animateFloat(self.objectWithAnimationData, animPath, animId, defaultValue)

    def transferAnimatableInteger(self, fieldName):
        """ Helper method"""
        animationReference = getattr(self.m3Object, fieldName)
        setattr(self.blenderObject, fieldName, animationReference.initValue)
        animationHeader = animationReference.header
        animId = animationHeader.animId
        defaultValue = animationReference.initValue
        self.importer.animateInteger(self.objectWithAnimationData, self.animPathPrefix, fieldName, animId, defaultValue)

    def transferAnimatableInt16(self, fieldName):
        self.transferAnimatableInteger(fieldName)

    def transferAnimatableUInt16(self, fieldName):
        self.transferAnimatableInteger(fieldName)

    def transferAnimatableUInt8(self, fieldName):
        self.transferAnimatableInteger(fieldName)

    def transferAnimatableUInt32(self, fieldName):
        self.transferAnimatableInteger(fieldName)

    def transferAnimatableBooleanBasedOnSDU3(self, fieldName):
        self.transferAnimatableInteger(fieldName)

    def transferAnimatableBooleanBasedOnSDFG(self, fieldName):
        self.transferAnimatableInteger(fieldName)

    def transferFloat(self, fieldName, sinceVersion=None, tillVersion=None):
        if (tillVersion is not None) and (self.m3Version > tillVersion):
            return
        if (sinceVersion is not None) and (self.m3Version < sinceVersion):
            return
        setattr(self.blenderObject, fieldName, getattr(self.m3Object, fieldName))

    def transferInt(self, fieldName, sinceVersion=None, tillVersion=None):
        if (tillVersion is not None) and (self.m3Version > tillVersion):
            return
        if (sinceVersion is not None) and (self.m3Version < sinceVersion):
            return
        setattr(self.blenderObject, fieldName, getattr(self.m3Object, fieldName))

    def transferString(self, fieldName):
        value = getattr(self.m3Object, fieldName)
        if value is None:
            value = ""
        setattr(self.blenderObject, fieldName, value)

    def transferBoolean(self, fieldName, tillVersion=None):
        if (tillVersion is not None) and (self.m3Version > tillVersion):
            return
        integerValue = getattr(self.m3Object, fieldName)
        if integerValue == 0:
            setattr(self.blenderObject, fieldName, False)
        elif integerValue == 1:
            setattr(self.blenderObject, fieldName, True)
        else:
            print("WARNING: %s was neither 0 nor 1" % fieldName)

    def transferBit(self, m3FieldName, bitName, sinceVersion=None):
        if (sinceVersion is not None) and (self.m3Version < sinceVersion):
            return
        setattr(self.blenderObject, bitName, self.m3Object.getNamedBit(m3FieldName, bitName))

    def transferBitEnum(self, m3FieldName, bitName, sinceVersion=None):
        if (sinceVersion is not None) and (self.m3Version < sinceVersion):
            return
        value = self.m3Object.getNamedBit(m3FieldName, bitName)
        value = "0" if value is False else "1"
        setattr(self.blenderObject, bitName, value)

    def transferMultipleBits(self, m3FieldName, bNameList=None):
        field = self.m3Object.structureDescription.nameToFieldMap[m3FieldName]
        if bNameList is None:
            bNameList = [x for x in field.bitMaskMap]
        for bitName in bNameList:
            self.transferBit(m3FieldName, bitName)

    def transfer16Bits(self, fieldName):
        integerValue = getattr(self.m3Object, fieldName)
        vector = getattr(self.blenderObject, fieldName)
        for bitIndex in range(0, 16):
            mask = 1 << bitIndex
            vector[bitIndex] = (mask & integerValue) > 0

    def transfer32Bits(self, fieldName):
        integerValue = getattr(self.m3Object, fieldName)
        vector = getattr(self.blenderObject, fieldName)
        for bitIndex in range(0, 32):
            mask = 1 << bitIndex
            vector[bitIndex] = (mask & integerValue) > 0

    def transferAnimatableVector3(self, fieldName, sinceVersion=None):
        if (sinceVersion is not None) and (self.m3Version < sinceVersion):
            return
        animationReference = getattr(self.m3Object, fieldName)
        setattr(self.blenderObject, fieldName, toBlenderVector3(animationReference.initValue))
        animationHeader = animationReference.header
        animId = animationHeader.animId
        animPath = self.animPathPrefix + fieldName
        defaultValue = animationReference.initValue
        self.importer.animateVector3(self.objectWithAnimationData, animPath, animId, defaultValue)

    def transferAnimatableVector2(self, fieldName):
        animationReference = getattr(self.m3Object, fieldName)
        setattr(self.blenderObject, fieldName, toBlenderVector2(animationReference.initValue))
        animationHeader = animationReference.header
        animId = animationHeader.animId
        animPath = self.animPathPrefix + fieldName
        defaultValue = animationReference.initValue
        self.importer.animateVector2(self.objectWithAnimationData, animPath, animId, defaultValue)

    def transferAnimatableColor(self, fieldName):
        animationReference = getattr(self.m3Object, fieldName)
        initValue = toBlenderColorVector(animationReference.initValue)
        # without alpha
        if len(getattr(self.blenderObject, fieldName)) == 3:
            setattr(self.blenderObject, fieldName, [*initValue][:3])
        else:
            setattr(self.blenderObject, fieldName, initValue)
        animationHeader = animationReference.header
        animId = animationHeader.animId
        animPath = self.animPathPrefix + fieldName
        defaultValue = animationReference.initValue
        self.importer.animateColor(self.objectWithAnimationData, animPath, animId, defaultValue)

    def transferAnimatableBoundings(self):
        animationReference = self.m3Object
        animationHeader = animationReference.header
        animId = animationHeader.animId
        boundingsObject = self.blenderObject
        animPathMinBorder = self.animPathPrefix + "minBorder"
        animPathMaxBorder = self.animPathPrefix + "maxBorder"
        animPathRadius = self.animPathPrefix + "radius"
        m3InitValue = animationReference.initValue
        boundingsObject.minBorder = toBlenderVector3(m3InitValue.minBorder)
        boundingsObject.maxBorder = toBlenderVector3(m3InitValue.maxBorder)
        boundingsObject.radius = m3InitValue.radius
        minBorderDefault = toBlenderVector3(m3InitValue.minBorder)
        maxBorderDefault = toBlenderVector3(m3InitValue.maxBorder)
        radiusDefault = m3InitValue.radius
        self.importer.animateBoundings(self.objectWithAnimationData, animPathMinBorder, animPathMaxBorder, animPathRadius, animId, minBorderDefault, maxBorderDefault, radiusDefault)

    def transferEnum(self, fieldName, sinceVersion=None):
        if (sinceVersion is not None) and (self.m3Version < sinceVersion):
            return
        if getattr(self.m3Object, fieldName) == 0xFFFFFFFF:
            return
        value = str(getattr(self.m3Object, fieldName))
        setattr(self.blenderObject, fieldName, value)


class AnimationTempData:
    def __init__(self, animIdToTimeValueMap, animationIndex):
        self.animIdToTimeValueMap = animIdToTimeValueMap
        # The animation object can't be stored in this structure
        # as it seems to get invalid when the mode changes
        # To avoid a blender crash an index is used to obtain a valid instance of the animation
        self.animationIndex = animationIndex


class Importer:

    def importM3BasedOnM3ImportOptions(self, scene: bt.Scene):
        fileName = scene.m3_import_options.path
        self.contentPreset = scene.m3_import_options.contentPreset
        self.rootDirectory = scene.m3_import_options.rootDirectory
        if (self.rootDirectory == ""):
            self.rootDirectory = path.dirname(fileName)
        self.scene = scene
        # print('loadModel', timeit(lambda: m3.loadModel(fileName), number=1))
        self.model = m3.loadModel(fileName)
        self.sequenceNameAndSTCIndexToAnimIdSet = {}
        self.armature: bpy.types.Armature = None
        self.armatureObject: bpy.types.Object = None
        self.boneNames = []

        scene.render.fps = FRAME_RATE
        self.animations = []
        self.animIdToLongAnimIdMap = {}

        if self.contentPreset == cm.M3ImportContentPreset.Everything:
            # clear existing animation ids so that they can't conflict with new ones:
            self.scene.m3_animation_ids.clear()
            self.storeModelId()
            self.createAnimations()
            self.importVisibilityTest()

        if self.contentPreset in [cm.M3ImportContentPreset.MeshMaterialsRig, cm.M3ImportContentPreset.Everything]:
            if scene.m3_import_options.armatureObject is not None:
                self.armatureObject = scene.m3_import_options.armatureObject
                self.armature = self.armatureObject.data
            else:
                self.armature = bpy.data.armatures.new(name="Armature")

            if not self.armatureObject:
                self.createArmatureObject()
            else:
                scene.view_layers[0].objects.active = self.armatureObject
                self.armatureObject.select_set(True)

            self.createBones()
        elif self.contentPreset in [cm.M3ImportContentPreset.MeshMaterialsVG]:
            self.boneNames = [*map(lambda x: x.name, self.model.bones)]

        self.createMaterials()

        if self.contentPreset == cm.M3ImportContentPreset.Everything:
            self.createCameras()
            self.createFuzzyHitTests()
            self.initTightHitTest()
            self.createParticleSystems()
            self.createRibbons()
            self.createForces()
            self.createRigidBodies()
            self.createLights()
            self.createBillboardBehaviors()
            self.createInverseKinematicChains()
            self.createTurretBehaviors()
            self.createPhysicsJoints()
            self.createAttachmentPoints()
            self.createProjections()
            self.createWarps()

        # print('createMesh', timeit(lambda: self.createMesh(), number=1))
        self.createMesh()

        if self.contentPreset == cm.M3ImportContentPreset.Everything:
            # init stcs of animations at last
            # when all animation properties are known
            self.initSTCsOfAnimations()

            if len(scene.m3_animations) >= 1:
                scene.m3_animation_index = -1
                scene.m3_animation_index = 0

        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')
        if bpy.ops.object.select_all.poll():
            bpy.ops.object.select_all(action='DESELECT')

    def addAnimIdData(self, animId, objectId, animPath):
        longAnimId = shared.getLongAnimIdOf(objectId, animPath)
        self.animIdToLongAnimIdMap[animId] = longAnimId
        animIdData = self.scene.m3_animation_ids.add()
        animIdData.animIdMinus2147483648 = animId - 2147483648
        animIdData.longAnimId = longAnimId

    def storeModelId(self):
        self.addAnimIdData(self.model.uniqueUnknownNumber, objectId=(shared.animObjectIdModel), animPath="")

    def createArmatureObject(self):
        # bpy.ops.object.mode_set(mode='OBJECT')
        # alternative: armature = bpy.ops.object.armature_add(view_align=False,enter_editmode=False, location=location, rotation=(0,0,0), layers=firstLayerOnly)
        scene = bpy.context.scene
        armatureObject = bpy.data.objects.new("Armature Object", self.armature)
        armatureObject.location = scene.cursor.location
        scene.collection.objects.link(armatureObject)
        scene.view_layers[0].objects.active = armatureObject
        armatureObject.select_set(True)
        self.armatureObject = armatureObject

    def createBones(self):
        """ Imports the bones

        About the bone import:
        Let m_i be the matrix which does the rotation, scale and translation specified in the m3 file for a given bone i
        and b_i the bind matrix (current name: absoluteInverseBoneRestPositions) of that bone i.

        Since the matrix m_i is relative to it's parent bone, the absolut transformation done by a bone 2 to a vertex can be calculated with:
        F_2 = m_0 * m_1 * m_2 * b_2 where bone 1 is the parent of bone 2 and bone 0 is the parent of bone 1

        The bone i in blender should have then the transformation F_i plus maybe a rotation fix r_i to have bones point to each other:
        f_2 = F_2 * r_2 = m_0 * m_ 1 * m_2 * b_2 * r_2


        In blender however there is the concept of a rest position of an armature.
        A bone like it's seen in Blender's edit mode has an absolute transformation matrix
        This absolute transformation matrix E_i of a bone i can be used to calculate a relative matrix called e_i:
        E_i = E_parent * e_i <=> e_i = E_parent^-1 * E_i
        The rotation, location and scale specified in the pose mode can be used to calculate a relative pose matrix p_i for a bone i
        For a bone 2 with parent 1, and grandparent 0 the final transformation gets calculated like this:
        f_2 = (e_0 * p_0) * (e_1 * p_1) * (e_2 * p_2)
        The goal is now to determine p_i so that f_2 is the same as:
        f_2 = m_0 * m_1 * m_2 * b_2 * r_2 <=>
        f_2 = E * m_0 * E * m_1 * E * m_2 * b_2 * r_2 <=>
        f_2 = (e_0 * e_0^-1) * m_0 * (b_0 * r_0 * e_1 * e_1^-1 * r_0^-1 * b_0^-1) * m_1 * (b_1 * r_1 * e_2 * e_2^-1 * r_1^-1 * b_1^-1) * m_2 * b_2 * r_2)  <=>
        f_2 = e_0 * (e_0^-1 * m_0 * b_0 * r_0) * e_1 * (e_1^-1 * r_0^-1 * b_0^-1 * m_1 * b_1 * r_1) * e_2 * (e_2^-1 * r_1^-1 * b_1^-1 * m_2 * b_2  * r_2)
              \------------------------------/         \------------------------------------------/         \-------------------------------------------/
                         p0                                             p1                                                        p2
        thus:
        p_0 = (e_0^-1  * m_0 * b_0 * r_0)
        p_1 = (e_1^-1 * r_0^-1 * b_0^-1 * m_1 * b_1 * r_1)
        p_2 = (e_2^-1 * r_1^-1 * b_1^-1 * m_2 * b_2 * r_2)


        In the following code is
        r_i = rotFixMatrix
        e_i = relEditBoneMatrices[i]
        """
        model = self.model
        self.adjustM3BoneNames(model)
        # print("Creating bone structure in rest position")

        absoluteBoneRestPositions = determineAbsoluteBoneRestPositions(model)

        bpy.ops.object.mode_set(mode='EDIT')
        checkOrder(model.bones)

        heads = list(m.translation for m in absoluteBoneRestPositions)

        self.scene.m3_import_options.recalculateRestPositionBones = True

        # In blender the edit bone with the vector (0,1,0) stands for a idenity matrix
        # So the second column of a edit bone matrix represents the bone vector
        boneDirectionVectors = list(m.col[1].to_3d().normalized() for m in absoluteBoneRestPositions)
        tails = determineTails(model.bones, heads, boneDirectionVectors)
        rolls = determineRolls(absoluteBoneRestPositions, heads, tails)

        bindScales = self.determineBindScales()
        bindScaleMatrices = self.scaleVectorsToMatrices(bindScales)

        editBones = self.createEditBones(model.bones, heads, tails, rolls, bindScales)

        relEditBoneMatrices = self.determineRelEditBoneMatrices(model.bones, editBones)

        # print("Adjusting pose bones")
        bpy.ops.object.mode_set(mode='POSE')
        self.adjustPoseBones(model.bones, relEditBoneMatrices, bindScaleMatrices)

    def adjustM3BoneNames(self, model):

        def adjustM3BoneNamePrefix(bone, prefix, unwantedPrefixes):
            if bone.name.startswith(prefix):
                return
            for unwantedPrefix in unwantedPrefixes:
                if not bone.name.startswith(unwantedPrefix):
                    continue

                bone.name = bone.name[len(unwantedPrefix):]
                if bone.name == "":
                    bone.name == "Null"

                bone.name = prefix + bone.name
                return

        for ii, bone in enumerate(model.bones):
            adjustM3BoneNamePrefix(bone, shared.star2ParticlePrefix, ["P_", "MR3_Particle_", "SC2Particles"])
            adjustM3BoneNamePrefix(bone, shared.star2RibbonPrefix, ["SC2SplRbn", "SC2Ribbon"])
            adjustM3BoneNamePrefix(bone, shared.lightPrefixMap["1"], ["SC2Omni"])
            adjustM3BoneNamePrefix(bone, shared.lightPrefixMap["2"], ["SC2Spot"])
            adjustM3BoneNamePrefix(bone, shared.star2ForcePrefix, ["_Force"])
            adjustM3BoneNamePrefix(bone, shared.star2ProjectionPrefix, [])
            adjustM3BoneNamePrefix(bone, shared.star2WarpPrefix, [])

    def adjustPoseBones(self, m3Bones, relEditBoneMatrices, bindScaleMatrices):
        index = 0
        for bone, relEditBoneMatrix, bindMatrix in zip(m3Bones, relEditBoneMatrices, bindScaleMatrices):

            poseBone = self.armatureObject.pose.bones[self.boneNames[index]]
            scale = toBlenderVector3(bone.scale.initValue)
            rotation = toBlenderQuaternion(bone.rotation.initValue)
            location = toBlenderVector3(bone.location.initValue)

            if bone.parent != -1:
                # TODO perforamcne optimization: cache bindScaleMatrices[bone.parent].inverted()
                # TODO find out why it's just the scale that need to be applied
                leftCorrectionMatrix = relEditBoneMatrix.inverted() @ shared.rotFixMatrixInverted @ bindScaleMatrices[bone.parent].inverted()
            else:
                leftCorrectionMatrix = relEditBoneMatrix.inverted()
            rightCorrectionMatrix = bindMatrix @ shared.rotFixMatrix

            poseBoneTransform = shared.locRotScaleMatrix(location, rotation, scale)
            poseBoneTransform = leftCorrectionMatrix @ poseBoneTransform @ rightCorrectionMatrix
            location, rotation, scale = poseBoneTransform.decompose()

            poseBone.scale = scale
            poseBone.rotation_quaternion = rotation
            poseBone.location = location
            self.animateBone(index, bone, leftCorrectionMatrix, rightCorrectionMatrix, location, rotation, scale)

            index += 1

    def determineBindScales(self):
        bindScales = []
        for inverseBoneRestPosition in self.model.absoluteInverseBoneRestPositions:
            matrix = toBlenderMatrix(inverseBoneRestPosition.matrix)
            location, rotation, scale = matrix.decompose()
            bindScales.append(scale)
        return bindScales

    def scaleVectorsToMatrices(self, scaleVectors):
        scaleMatrices = []
        for scaleVector in scaleVectors:
            scaleMatrices.append(shared.scaleVectorToMatrix(scaleVector))
        return scaleMatrices

    def fix180DegreeRotationsInMapWithKeys(self, timeToRotationMap, timeEntries):
        previousRotation = None
        for timeInMS in timeEntries:
            rotation = timeToRotationMap.get(timeInMS)
            if previousRotation is not None:
                shared.smoothQuaternionTransition(previousQuaternion=previousRotation, quaternionToFix=rotation)
            previousRotation = rotation

    def applyCorrectionToLocRotScaleMaps(self, leftCorrectionMatrix, rightCorrectionMatrix, timeToLocationMap, timeToRotationMap, timeToScaleMap, timeEntries):
        for timeInMS in timeEntries:
            location = timeToLocationMap.get(timeInMS)
            rotation = timeToRotationMap.get(timeInMS)
            scale = timeToScaleMap.get(timeInMS)

            location = toBlenderVector3(location)
            rotation = toBlenderQuaternion(rotation)
            scale = toBlenderVector3(scale)
            relSpecifiedMatrix = shared.locRotScaleMatrix(location, rotation, scale)

            newMatrix = leftCorrectionMatrix @ relSpecifiedMatrix @ rightCorrectionMatrix
            location, rotation, scale = newMatrix.decompose()
            timeToLocationMap[timeInMS] = location
            timeToRotationMap[timeInMS] = rotation
            timeToScaleMap[timeInMS] = scale

    def animateBone(self, boneIndex, m3Bone, leftCorrectionMatrix, rightCorrectionMatrix, defaultLocation, defaultRotation, defaultScale):
        boneName = self.boneNames[boneIndex]
        locationAnimId = m3Bone.location.header.animId
        locationAnimPath = 'pose.bones["%s"].location' % boneName
        self.addAnimIdData(locationAnimId, objectId=shared.animObjectIdArmature, animPath=locationAnimPath)

        rotationAnimId = m3Bone.rotation.header.animId
        rotationAnimPath = 'pose.bones["%s"].rotation_quaternion' % boneName
        self.addAnimIdData(rotationAnimId, objectId=shared.animObjectIdArmature, animPath=rotationAnimPath)

        scaleAnimId = m3Bone.scale.header.animId
        scaleAnimPath = 'pose.bones["%s"].scale' % boneName
        self.addAnimIdData(scaleAnimId, objectId=shared.animObjectIdArmature, animPath=scaleAnimPath)

        for animationTempData in self.animations:
            animIdToTimeValueMap = animationTempData.animIdToTimeValueMap
            action = self.createOrGetActionFor(self.armatureObject, animationTempData)

            timeToLocationMap = animIdToTimeValueMap.get(locationAnimId, {0: m3Bone.location.initValue})
            timeToLocationMap = convertToBlenderVector3Map(timeToLocationMap)

            timeToRotationMap = animIdToTimeValueMap.get(rotationAnimId, {0: m3Bone.rotation.initValue})
            timeToRotationMap = convertToBlenderQuaternionMap(timeToRotationMap)

            timeToScaleMap = animIdToTimeValueMap.get(scaleAnimId, {0: m3Bone.scale.initValue})
            timeToScaleMap = convertToBlenderVector3Map(timeToScaleMap)

            rotKeys = list(timeToRotationMap.keys())
            rotKeys.sort()
            self.fix180DegreeRotationsInMapWithKeys(timeToRotationMap, rotKeys)

            timeEntries = []
            timeEntries.extend(timeToLocationMap.keys())
            timeEntries.extend(timeToRotationMap.keys())
            timeEntries.extend(timeToScaleMap.keys())
            timeEntries = list(set(timeEntries))  # elimate duplicates
            timeEntries.sort()

            extendTimeToVectorMapByInterpolation(timeToLocationMap, timeEntries)
            extendTimeToQuaternionMapByInterpolation(timeToRotationMap, timeEntries)
            extendTimeToVectorMapByInterpolation(timeToScaleMap, timeEntries)

            self.applyCorrectionToLocRotScaleMaps(leftCorrectionMatrix, rightCorrectionMatrix, timeToLocationMap, timeToRotationMap, timeToScaleMap, timeEntries)

            self.fix180DegreeRotationsInMapWithKeys(timeToRotationMap, timeEntries)

            frames = []
            for timeInMS in timeEntries:
                frames.append(msToFrame(timeInMS))

            group = boneName
            if locationAnimId in animIdToTimeValueMap:
                locXCurve = action.fcurves.new(locationAnimPath, index=0, action_group=group)
                locYCurve = action.fcurves.new(locationAnimPath, index=1, action_group=group)
                locZCurve = action.fcurves.new(locationAnimPath, index=2, action_group=group)
                for timeInMS, frame in zip(timeEntries, frames):
                    location = timeToLocationMap.get(timeInMS)
                    insertLinearKeyFrame(locXCurve, frame, location.x)
                    insertLinearKeyFrame(locYCurve, frame, location.y)
                    insertLinearKeyFrame(locZCurve, frame, location.z)

            if rotationAnimId in animIdToTimeValueMap:
                rotWCurve = action.fcurves.new(rotationAnimPath, index=0, action_group=group)
                rotXCurve = action.fcurves.new(rotationAnimPath, index=1, action_group=group)
                rotYCurve = action.fcurves.new(rotationAnimPath, index=2, action_group=group)
                rotZCurve = action.fcurves.new(rotationAnimPath, index=3, action_group=group)
                for timeInMS, frame in zip(timeEntries, frames):
                    rotation = timeToRotationMap.get(timeInMS)
                    insertLinearKeyFrame(rotWCurve, frame, rotation.w)
                    insertLinearKeyFrame(rotXCurve, frame, rotation.x)
                    insertLinearKeyFrame(rotYCurve, frame, rotation.y)
                    insertLinearKeyFrame(rotZCurve, frame, rotation.z)

            if scaleAnimId in animIdToTimeValueMap:
                scaXCurve = action.fcurves.new(scaleAnimPath, index=0, action_group=group)
                scaYCurve = action.fcurves.new(scaleAnimPath, index=1, action_group=group)
                scaZCurve = action.fcurves.new(scaleAnimPath, index=2, action_group=group)
                for timeInMS, frame in zip(timeEntries, frames):
                    scale = timeToScaleMap.get(timeInMS)
                    insertLinearKeyFrame(scaXCurve, frame, scale.x)
                    insertLinearKeyFrame(scaYCurve, frame, scale.y)
                    insertLinearKeyFrame(scaZCurve, frame, scale.z)

    def importVisibilityTest(self):
        # print("Imported bounding radius %s" % self.model.boundings.radius)
        self.scene.m3_visibility_test.radius = self.model.boundings.radius
        minBorder = toBlenderVector3(self.model.boundings.minBorder)
        maxBorder = toBlenderVector3(self.model.boundings.maxBorder)
        self.scene.m3_visibility_test.center = (minBorder + maxBorder) / 2.0
        self.scene.m3_visibility_test.size = maxBorder - minBorder
        self.scene.m3_visibility_test.radius = self.model.boundings.radius

    def createLayers(self, scene, material, m3Material, materialAnimPathPrefix):
        for layerFieldName in shared.layerFieldNamesOfM3Material(m3Material):
            m3Layer = getattr(m3Material, layerFieldName)[0]
            layerIndex = len(material.layers)
            materialLayer = material.layers.add()
            materialLayer.name = shared.layerFieldNameToNameMap[layerFieldName]
            animPathPrefix = "%slayers[%s]." % (materialAnimPathPrefix, layerIndex)
            layerTransferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=materialLayer, m3Object=m3Layer)
            shared.transferMaterialLayer(layerTransferer)
            materialLayer.fresnelMax = m3Layer.fresnelMin + m3Layer.fresnelMaxOffset
            if m3Layer.structureDescription.structureVersion >= 25:
                materialLayer.fresnelMaskX = 1.0 - m3Layer.fresnelInvertedMaskX
                materialLayer.fresnelMaskY = 1.0 - m3Layer.fresnelInvertedMaskY
                materialLayer.fresnelMaskZ = 1.0 - m3Layer.fresnelInvertedMaskZ

    def createMaterials(self):
        # print("Loading materials")
        scene = self.scene
        self.initMaterialReferenceIndexToNameMap()

        if self.contentPreset in [cm.M3ImportContentPreset.MeshMaterials, cm.M3ImportContentPreset.MeshMaterialsRig]:
            # Import only indices of materials used by meshes:
            matRefIndicesToImport = set()
            for division in self.model.divisions:
                for m3Object in division.objects:
                    matRefIndicesToImport.add(m3Object.materialReferenceIndex)
        else:
            # Import all materials:
            matRefIndicesToImport = set(range(len(self.model.materialReferences)))

        for materialReferenceIndex, m3MaterialReference in enumerate(self.model.materialReferences):
            if materialReferenceIndex not in matRefIndicesToImport:
                continue
            materialType = m3MaterialReference.materialType
            m3MaterialIndex = m3MaterialReference.materialIndex
            m3MaterialFieldName = shared.m3MaterialFieldNames[materialType]
            blenderMaterialsFieldName = cm.blenderMaterialsFieldNames[materialType]
            transferMethod = shared.materialTransferMethods[materialType]

            m3Material = getattr(self.model, m3MaterialFieldName)[m3MaterialIndex]
            blenderMaterialCollection = getattr(scene, blenderMaterialsFieldName)
            blenderMaterialIndex = len(blenderMaterialCollection)
            material = blenderMaterialCollection.add()
            animPathPrefix = blenderMaterialsFieldName + "[%s]." % blenderMaterialIndex
            materialTransferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=material, m3Object=m3Material)
            transferMethod(materialTransferer)
            material.name = self.materialReferenceIndexToNameMap[materialReferenceIndex]
            self.createLayers(scene, material, m3Material, animPathPrefix)
            blenderMaterialReferenceIndex = len(scene.m3_material_references)
            material.materialReferenceIndex = blenderMaterialReferenceIndex
            materialReference = scene.m3_material_references.add()
            materialReference.name = material.name
            materialReference.materialType = materialType
            materialReference.materialIndex = blenderMaterialIndex
            if hasattr(m3Material, "sections"):  # Currently only composite materials have sections
                for sectionIndex, m3Section in enumerate(m3Material.sections):
                    section = material.sections.add()
                    sectionAnimPathPrefix = animPathPrefix + ".sections[%s]." % sectionIndex
                    materialSectionTransferer = M3ToBlenderDataTransferer(self, scene, sectionAnimPathPrefix, blenderObject=section, m3Object=m3Section)
                    shared.transferCompositeMaterialSection(materialSectionTransferer)
                    section.name = self.getNameOfMaterialWithReferenceIndex(m3Section.materialReferenceIndex)

    def initMaterialReferenceIndexToNameMap(self):
        uniqueNameFinder = shared.UniqueNameFinder()
        uniqueNameFinder.markNamesOfCollectionAsUsed(self.scene.m3_material_references)

        self.materialReferenceIndexToNameMap = {}
        for materialReferenceIndex, materialReference in enumerate(self.model.materialReferences):
            wantedName = self.getMaterialNameByM3MaterialReference(materialReference)
            freeName = uniqueNameFinder.findNameAndMarkAsUsedLike(wantedName)
            self.materialReferenceIndexToNameMap[materialReferenceIndex] = freeName

    def getMaterialNameByM3MaterialReference(self, materialReference):
        materialIndex = materialReference.materialIndex
        materialType = materialReference.materialType
        m3MaterialFieldName = shared.m3MaterialFieldNames[materialType]
        m3MaterialList = getattr(self.model, m3MaterialFieldName)
        return m3MaterialList[materialIndex].name

    def createCameras(self):
        scene = bpy.context.scene
        showCameras = scene.m3_bone_visiblity_options.showCameras
        # print("Loading cameras")

        for m3Camera in self.model.cameras:
            camera = scene.m3_cameras.add()

            animPathPrefix = "m3_cameras[%s]." % (len(scene.m3_cameras) - 1)
            transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=camera, m3Object=m3Camera)
            shared.transferCamera(transferer)

            blenderBoneName = self.boneNames[m3Camera.boneIndex]
            m3Bone = self.model.bones[m3Camera.boneIndex]
            if m3Bone.name != m3Camera.name:
                raise Exception("Bone of camera '%s' had different name: '%s'" % (camera.name, m3Bone.name))
            camera.name = blenderBoneName

            bone = self.armature.bones[blenderBoneName]
            bone.hide = not showCameras

    def intShapeObject(self, blenderShapeObject, m3ShapeObject):
        scene = bpy.context.scene
        blenderBoneName = self.boneNames[m3ShapeObject.boneIndex]
        blenderShapeObject.boneName = blenderBoneName
        if m3ShapeObject.boneIndex != -1:
            if blenderBoneName == shared.tightHitTestBoneName:
                showBone = scene.m3_bone_visiblity_options.showTightHitTest
            else:
                showBone = scene.m3_bone_visiblity_options.showFuzzyHitTests
            bone = self.armature.bones[blenderBoneName]
            bone.hide = not showBone
        matrix = toBlenderMatrix(m3ShapeObject.matrix)
        offset, rotation, scale = matrix.decompose()
        blenderShapeObject.offset = offset
        blenderShapeObject.rotationEuler = rotation.to_euler("XYZ")
        blenderShapeObject.scale = scale
        transferer = M3ToBlenderDataTransferer(self, None, None, blenderObject=blenderShapeObject, m3Object=m3ShapeObject)
        shared.transferFuzzyHitTest(transferer)

    def m3Vector4IsZero(self, v):
        return v.x == 0.0 and v.y == 0.0 and v.z == 0.0 and v.w == 0.0

    def initTightHitTest(self):
        # print("Loading tight hit test shape")
        scene = bpy.context.scene
        m = self.model.tightHitTest.matrix
        matrixIsZero = self.m3Vector4IsZero(m.x) and self.m3Vector4IsZero(m.y) and self.m3Vector4IsZero(m.z) and self.m3Vector4IsZero(m.w)
        if matrixIsZero:
            pass  # known bug of some unoffical exporters
        else:
            self.intShapeObject(scene.m3_tight_hit_test, self.model.tightHitTest)

    def createFuzzyHitTests(self):
        scene = bpy.context.scene
        # print("Loading fuzzy hit tests")
        for index, m3FuzzyHitTest in enumerate(self.model.fuzzyHitTestObjects):
            fuzzyHitTest = scene.m3_fuzzy_hit_tests.add()
            self.intShapeObject(fuzzyHitTest, m3FuzzyHitTest)

    def createParticleSystems(self):
        scene = bpy.context.scene
        showParticleSystems = scene.m3_bone_visiblity_options.showParticleSystems
        # print("Loading particle systems")

        uniqueNameFinder = shared.UniqueNameFinder()
        uniqueNameFinder.markNamesOfCollectionAsUsed(self.scene.m3_particle_systems)
        for particleSystem in self.scene.m3_particle_systems:
            uniqueNameFinder.markNamesOfCollectionAsUsed(particleSystem.copies)

        m3IndexToParticleSystemMap = {}
        for particleSystemIndex, m3ParticleSystem in enumerate(self.model.particles):
            blenderBoneName = self.boneNames[m3ParticleSystem.boneIndex]
            wantedName = blenderBoneName[len(shared.star2ParticlePrefix):]
            name = uniqueNameFinder.findNameAndMarkAsUsedLike(wantedName)
            m3IndexToParticleSystemMap[particleSystemIndex] = name

        for particleSystemIndex, m3ParticleSystem in enumerate(self.model.particles):
            particleSystem = scene.m3_particle_systems.add()
            particleSystem.bl_update = False

            blenderBoneName = self.boneNames[m3ParticleSystem.boneIndex]

            animPathPrefix = "m3_particle_systems[%s]." % (len(scene.m3_particle_systems) - 1)
            transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=particleSystem, m3Object=m3ParticleSystem)
            shared.transferParticleSystem(transferer)

            particleSystem.materialName = self.getNameOfMaterialWithReferenceIndex(m3ParticleSystem.materialReferenceIndex)
            if hasattr(m3ParticleSystem, "forceChannelsCopy") and m3ParticleSystem.forceChannelsCopy != m3ParticleSystem.forceChannels:
                pass
                # print("Warning: Unexpected model content: forceChannels != forceChannelsCopy")

            if m3ParticleSystem.structureDescription.structureVersion < 17:
                # in >= 17 there is a field which specifies the exact type
                # the flags are then redundant

                if m3ParticleSystem.getNamedBit("flags", "bezSmoothSize"):
                    particleSystem.sizeSmoothingType = "2"
                elif m3ParticleSystem.getNamedBit("flags", "smoothSize"):
                    particleSystem.sizeSmoothingType = "1"
                else:
                    particleSystem.sizeSmoothingType = "0"

                if m3ParticleSystem.getNamedBit("flags", "bezSmoothColor"):
                    particleSystem.colorSmoothingType = "2"
                elif m3ParticleSystem.getNamedBit("flags", "smoothColor"):
                    particleSystem.colorSmoothingType = "1"
                else:
                    particleSystem.colorSmoothingType = "0"

                if m3ParticleSystem.getNamedBit("flags", "bezSmoothRotation"):
                    particleSystem.rotationSmoothingType = "2"
                elif m3ParticleSystem.getNamedBit("flags", "smoothRotation"):
                    particleSystem.rotationSmoothingType = "1"
                else:
                    particleSystem.rotationSmoothingType = "0"

            particleSystem.bl_update = True
            particleSystem.name = m3IndexToParticleSystemMap[particleSystemIndex]

            bone = self.armature.bones[blenderBoneName]
            bone.hide = not showParticleSystems

            for spawnPointIndex, m3SpawnPoint in enumerate(m3ParticleSystem.spawnPoints):
                spawnPoint = particleSystem.spawnPoints.add()
                spawnPointAnimPathPrefix = animPathPrefix + "spawnPoints[%d]." % spawnPointIndex
                transferer = M3ToBlenderDataTransferer(self, scene, spawnPointAnimPathPrefix, blenderObject=spawnPoint, m3Object=m3SpawnPoint)
                shared.transferSpawnPoint(transferer)

            if m3ParticleSystem.trailingParticlesIndex != -1:
                particleSystem.trailingParticlesName = m3IndexToParticleSystemMap.get(m3ParticleSystem.trailingParticlesIndex)

            for blenderCopyIndex, m3CopyIndex in enumerate(m3ParticleSystem.copyIndices):
                m3Copy = self.model.particleCopies[m3CopyIndex]
                copy = particleSystem.copies.add()

                copyAnimPathPrefix = animPathPrefix + "copies[%d]." % blenderCopyIndex
                transferer = M3ToBlenderDataTransferer(self, scene, copyAnimPathPrefix, blenderObject=copy, m3Object=m3Copy)
                shared.transferParticleSystemCopy(transferer)

                blenderBoneName = self.boneNames[m3Copy.boneIndex]
                wantedName = blenderBoneName[len(shared.star2ParticlePrefix):]
                copy.name = uniqueNameFinder.findNameAndMarkAsUsedLike(wantedName)

                bone = self.armature.bones[blenderBoneName]
                bone.hide = not showParticleSystems

    def createRibbons(self):
        scene = bpy.context.scene
        showRibbons = scene.m3_bone_visiblity_options.showRibbons
        # print("Loading particle systems")
        for m3Ribbon in self.model.ribbons:
            ribbon = scene.m3_ribbons.add()

            animPathPrefix = "m3_ribbons[%s]." % (len(scene.m3_ribbons) - 1)
            transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=ribbon, m3Object=m3Ribbon)
            shared.transferRibbon(transferer)

            blenderBoneName = self.boneNames[m3Ribbon.boneIndex]
            ribbon.name = blenderBoneName[len(shared.star2RibbonPrefix):]

            for ii, m3EndPoint in enumerate(m3Ribbon.endPoints):
                endPoint = ribbon.endPoints.add()
                endPoint.name = self.boneNames[m3EndPoint.boneIndex]

                endPointAnimPathPrefix = animPathPrefix + "endPoints[%d]." % ii
                transferer = M3ToBlenderDataTransferer(self, scene, endPointAnimPathPrefix, blenderObject=endPoint, m3Object=m3EndPoint)
                shared.transferRibbonEndPoint(transferer)

                bone = self.armature.bones[endPoint.name]
                bone.hide = not showRibbons

            bone = self.armature.bones[blenderBoneName]
            bone.hide = not showRibbons
            ribbon.materialName = self.getNameOfMaterialWithReferenceIndex(m3Ribbon.materialReferenceIndex)

    def createProjections(self):
        scene = bpy.context.scene
        # print("Loading projections")
        for m3Projection in self.model.projections:
            projection = scene.m3_projections.add()
            projection.bl_update = False

            animPathPrefix = "m3_projections[%s]." % (len(scene.m3_projections) - 1)
            transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=projection, m3Object=m3Projection)
            shared.transferProjection(transferer)

            projection.depth = m3Projection.boxTopZOffset.initValue - m3Projection.boxBottomZOffset.initValue
            projection.width = m3Projection.boxRightXOffset.initValue - m3Projection.boxLeftXOffset.initValue
            projection.height = m3Projection.boxBackYOffset.initValue - m3Projection.boxFrontYOffset.initValue
            projection.materialName = self.getNameOfMaterialWithReferenceIndex(m3Projection.materialReferenceIndex)

            projection.bl_update = True

            blenderBoneName = self.boneNames[m3Projection.boneIndex]
            projection.name = blenderBoneName[len(shared.star2ProjectionPrefix):]

            bone = self.armature.bones[blenderBoneName]
            bone.hide = not scene.m3_bone_visiblity_options.showProjections

    def createWarps(self):
        scene = bpy.context.scene
        # print("Loading warps")
        for m3Warp in self.model.warps:
            warp = scene.m3_warps.add()
            warp.bl_update = False

            animPathPrefix = "m3_warps[%s]." % (len(scene.m3_warps) - 1)
            transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=warp, m3Object=m3Warp)
            shared.transferWarp(transferer)

            warp.bl_update = True

            blenderBoneName = self.boneNames[m3Warp.boneIndex]
            warp.name = blenderBoneName[len(shared.star2WarpPrefix):]

            bone = self.armature.bones[blenderBoneName]
            bone.hide = not scene.m3_bone_visiblity_options.showWarps

    def createForces(self):
        scene = bpy.context.scene
        # print("Loading forces")
        for m3Force in self.model.forces:
            force = scene.m3_forces.add()
            force.bl_update = False

            animPathPrefix = "m3_forces[%s]." % (len(scene.m3_forces) - 1)
            transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=force, m3Object=m3Force)
            shared.transferForce(transferer)

            force.bl_update = True

            blenderBoneName = self.boneNames[m3Force.boneIndex]
            force.name = blenderBoneName[len(shared.star2ForcePrefix):]

            bone = self.armature.bones[blenderBoneName]
            bone.hide = not scene.m3_bone_visiblity_options.showForces

    def createRigidBodies(self):
        scene = bpy.context.scene
        # print("Loading rigid bodies")
        for m3RigidBody in self.model.rigidBodies:
            rigid_body = scene.m3_rigid_bodies.add()

            for physicsShapeIndex, m3PhysicsShape in enumerate(m3RigidBody.physicsShapes):
                physics_shape = rigid_body.physicsShapes.add()

                animPathPrefix = "m3_physics_shapes[%s]." % physicsShapeIndex
                physics_shape.name = "%d" % (physicsShapeIndex + 1)
                transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=physics_shape, m3Object=m3PhysicsShape)
                shared.transferPhysicsShape(transferer)

                matrix = toBlenderMatrix(m3PhysicsShape.matrix)
                offset, rotation, scale = matrix.decompose()
                physics_shape.offset = offset
                physics_shape.rotationEuler = rotation.to_euler("XYZ")
                physics_shape.scale = scale

                if physics_shape.shape in ["4", "5"]:  # convex hull or mesh

                    if m3PhysicsShape.structureDescription.structureVersion <= 1:
                        vertices = [(v.x, v.y, v.z) for v in m3PhysicsShape.vertices]

                        indices = range(0, len(m3PhysicsShape.faces), 3)
                        faces = [m3PhysicsShape.faces[i: i + 3] for i in indices]
                    # else:
                    #     print("Warning: Physical shape data has not been imported as it is to new")
                    #     faces = []
                    #     vertices = []
                    # Prevent Blender from crashing for real when the vertex data is invalid:
                    for f in faces:
                        if f[0] >= len(vertices) or f[1] >= len(vertices) or f[2] >= len(vertices):
                            raise Exception("A phsyical mesh is invalid")

                    mesh = bpy.data.meshes.new('PhysicsMesh')
                    mesh.from_pydata(vertices=vertices, faces=faces, edges=[])
                    mesh.update(calc_edges=True)
                    mesh.m3_physics_mesh = True

                    meshObject = bpy.data.objects.new('PhysicsMeshObject', mesh)
                    meshObject.location = scene.cursor.location
                    meshObject.show_name = True

                    scene.collection.objects.link(meshObject)

                    physics_shape.meshObjectName = meshObject.name

            animPathPrefix = "m3_rigid_bodies[%s]." % (len(scene.m3_rigid_bodies) - 1)
            transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=rigid_body, m3Object=m3RigidBody)
            shared.transferRigidBody(transferer)

            blenderBoneName = self.boneNames[m3RigidBody.boneIndex]
            rigid_body.nameOld = rigid_body.name = blenderBoneName

            # shared.updateBoneShapeOfRigidBody(scene, rigid_body)

            bone = self.armature.bones[rigid_body.name]
            bone.hide = not scene.m3_bone_visiblity_options.showPhysicsShapes

    def createLights(self):
        scene = bpy.context.scene
        showLights = scene.m3_bone_visiblity_options.showLights
        # print("Loading lights")
        for m3Light in self.model.lights:
            light = scene.m3_lights.add()
            light.bl_update = False

            animPathPrefix = "m3_lights[%s]." % (len(scene.m3_lights) - 1)

            transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=light, m3Object=m3Light)
            shared.transferLight(transferer)

            light.bl_update = True

            boneEntry = self.model.bones[m3Light.boneIndex]
            fullBoneName = boneEntry.name
            blenderBoneName = self.boneNames[m3Light.boneIndex]

            lightPrefix = shared.lightPrefixMap.get(str(m3Light.lightType))
            if blenderBoneName.startswith(lightPrefix):
                light.name = blenderBoneName[len(lightPrefix):]
            elif blenderBoneName.startswith("MR3_Light_"):
                light.name = blenderBoneName[len("MR3_Light_"):]
            else:
                # print("Warning: A light was bound to bone %s which does not start with %s" % (fullBoneName, lightPrefix))
                light.name = blenderBoneName

            # TODO ensure that name is unique; unique bone is not always enough
            # needs to be fixed for other objects too
            bone = self.armature.bones[light.boneName]
            bone.hide = not showLights

    def createBillboardBehaviors(self):
        scene = bpy.context.scene
        # print("Loading billboard behaviors")
        for m3BillboardBehavior in self.model.billboardBehaviors:
            billboardBehavior = scene.m3_billboard_behaviors.add()

            animPathPrefix = "m3_billboard_behaviors[%s]." % (len(scene.m3_billboard_behaviors) - 1)
            transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=billboardBehavior, m3Object=m3BillboardBehavior)
            shared.transferBillboardBehavior(transferer)

            blenderBoneName = self.boneNames[m3BillboardBehavior.boneIndex]
            billboardBehavior.name = blenderBoneName

    def createInverseKinematicChains(self):
        scene = bpy.context.scene
        # print("Loading inverse kinematic chains")
        for m3IkChain in self.model.inverseKinematicChains:
            ik = scene.m3_ik_chains.add()

            animPathPrefix = "m3_ik_chain[%s]." % (len(scene.m3_ik_chains) - 1)
            transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=ik, m3Object=m3IkChain)
            shared.transferIkChain(transferer)

            ik.name = "ikChain%s" % len(scene.m3_ik_chains)
            ik.boneName1 = self.boneNames[m3IkChain.boneIndex1]
            ik.boneName2 = self.boneNames[m3IkChain.boneIndex2]

    def createTurretBehaviors(self):
        scene = bpy.context.scene
        # print("Loading turret behaviors")
        for m3TurretBehavior in self.model.turretBehaviors:
            turret = scene.m3_turret_behaviors.add()
            turret.name = m3TurretBehavior.name

            for m3TurretBehaviorPartIndex in m3TurretBehavior.partIndex:
                m3TurretBehaviorPart = self.model.turretBehaviorParts[m3TurretBehaviorPartIndex]
                part = turret.parts.add()
                animPathPrefix = "m3_turret_behavior[%s].parts[%s]" % (len(scene.m3_turret_behaviors), len(turret.parts))
                transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=part, m3Object=m3TurretBehaviorPart)
                shared.transferTurretBehaviorPart(transferer)

                part.name = self.boneNames[m3TurretBehaviorPart.boneIndex]
                part.forwardX[0] = m3TurretBehaviorPart.forwardX.x
                part.forwardX[1] = m3TurretBehaviorPart.forwardX.y
                part.forwardX[2] = m3TurretBehaviorPart.forwardX.z
                part.forwardX[3] = m3TurretBehaviorPart.forwardX.w
                part.forwardY[0] = m3TurretBehaviorPart.forwardY.x
                part.forwardY[1] = m3TurretBehaviorPart.forwardY.y
                part.forwardY[2] = m3TurretBehaviorPart.forwardY.z
                part.forwardY[3] = m3TurretBehaviorPart.forwardY.w
                part.forwardZ[0] = m3TurretBehaviorPart.forwardZ.x
                part.forwardZ[1] = m3TurretBehaviorPart.forwardZ.y
                part.forwardZ[2] = m3TurretBehaviorPart.forwardZ.z
                part.forwardZ[3] = m3TurretBehaviorPart.forwardZ.w
                part.upX[0] = m3TurretBehaviorPart.upX.x
                part.upX[1] = m3TurretBehaviorPart.upX.y
                part.upX[2] = m3TurretBehaviorPart.upX.z
                part.upX[3] = m3TurretBehaviorPart.upX.w
                part.upY[0] = m3TurretBehaviorPart.upY.x
                part.upY[1] = m3TurretBehaviorPart.upY.y
                part.upY[2] = m3TurretBehaviorPart.upY.z
                part.upY[3] = m3TurretBehaviorPart.upY.w
                part.upZ[0] = m3TurretBehaviorPart.upZ.x
                part.upZ[1] = m3TurretBehaviorPart.upZ.y
                part.upZ[2] = m3TurretBehaviorPart.upZ.z
                part.upZ[3] = m3TurretBehaviorPart.upZ.w

    def createPhysicsJoints(self):
        # print("Loading physics joints")
        scene = bpy.context.scene

        for m3pj in self.model.physicsJoints:
            pj = scene.m3_physics_joints.add()
            pj.bl_update = False

            animPathPrefix = "m3_physics_joints[%s]." % (len(scene.m3_physics_joints) - 1)
            transferer = M3ToBlenderDataTransferer(self, scene, animPathPrefix, blenderObject=pj, m3Object=m3pj)
            shared.transferPhysicsJoint(transferer)

            pj.name = "Joint" + str(len(scene.m3_physics_joints) - 1)
            pj.boneName1 = self.boneNames[m3pj.boneIndex1]
            pj.boneName2 = self.boneNames[m3pj.boneIndex2]

            offset, rotation, scale = toBlenderMatrix(m3pj.matrix1).decompose()
            pj.offset1 = offset
            pj.rotation1 = rotation.to_euler("XYZ")
            offset, rotation, scale = toBlenderMatrix(m3pj.matrix2).decompose()
            pj.offset2 = offset
            pj.rotation2 = rotation.to_euler("XYZ")

            pj.bl_update = True

    def createAttachmentPoints(self):
        # print("Loading attachment points and volumes")
        scene = bpy.context.scene
        showAttachmentPoints = scene.m3_bone_visiblity_options.showAttachmentPoints
        boneIndexToM3AttachmentVolumeMap = {}
        for m3AttchmentVolume in self.model.attachmentVolumes:
            if m3AttchmentVolume.bone0 != m3AttchmentVolume.bone1 or m3AttchmentVolume.bone0 != m3AttchmentVolume.bone2:
                raise Exception("Can't handle a special attachment volume")
            boneIndex = m3AttchmentVolume.bone0
            if m3AttchmentVolume.type not in [0, 1, 2, 3, 4]:
                raise Exception("Unhandled attachment volume type %d" % m3AttchmentVolume.type)
            if boneIndex in boneIndexToM3AttachmentVolumeMap:
                raise Exception("Found two attachment volumes for one attachment points")
            boneIndexToM3AttachmentVolumeMap[boneIndex] = m3AttchmentVolume

        for attachmentPointIndex, m3AttachmentPoint in enumerate(self.model.attachmentPoints):
            boneIndex = m3AttachmentPoint.boneIndex
            boneEntry = self.model.bones[boneIndex]
            boneNameInBlender = self.boneNames[boneIndex]

            attachmentPoint = scene.m3_attachment_points.add()
            attachmentPoint.bl_update = False

            m3AttchmentVolume = boneIndexToM3AttachmentVolumeMap.get(boneIndex)
            if m3AttchmentVolume is None:
                attachmentPoint.volumeType = "-1"
            else:
                attachmentPoint.volumeType = str(m3AttchmentVolume.type)
                attachmentPoint.volumeSize0 = m3AttchmentVolume.size0
                attachmentPoint.volumeSize1 = m3AttchmentVolume.size1
                attachmentPoint.volumeSize2 = m3AttchmentVolume.size2

            attachmentPoint.bl_update = True

            prefixedName = m3AttachmentPoint.name
            if not prefixedName.startswith(shared.attachmentPointPrefix):
                pass
                # print("Warning: The name of the attachment %s does not start with %s" % (prefixedName, shared.attachmentPointPrefix))

            if boneEntry.name == boneNameInBlender:
                attachmentPoint.name = prefixedName[len(shared.attachmentPointPrefix):]
            else:
                # If the bone name was to long, or when there was already a bone with that name
                # Use the new bone name to determine the name
                attachmentPoint.name = shared.attachmentPointNameFromBoneName(boneNameInBlender)

            bone = self.armature.bones[attachmentPoint.boneName]
            bone.hide = not showAttachmentPoints

    def getNameOfMaterialWithReferenceIndex(self, materialReferenceIndex):
        return self.materialReferenceIndexToNameMap[materialReferenceIndex]

    def createMesh(self):
        model = self.model
        if model.getNamedBit("vFlags", "hasVertices") is not True:
            if len(self.model.vertices) > 0:
                raise Exception("Mesh claims to not have any vertices - expected buffer to be empty, but it isn't. size=%d" % len(self.model.vertices))
            return

        vertexClassName = "VertexFormat" + hex(self.model.vFlags)
        if vertexClassName not in m3.structures:
            raise Exception(
                "Vertex flags %s can't behandled yet. bufferSize=%d" % (
                    hex(self.model.vFlags),
                    len(self.model.vertices)
                ))

        vertexStructureDescription = m3.structures[vertexClassName].getVersion(0)

        numberOfVertices = len(self.model.vertices) // vertexStructureDescription.size
        m3Vertices = vertexStructureDescription.createInstances(buffer=self.model.vertices, count=numberOfVertices)

        for division in self.model.divisions:
            divisionFaceIndices = division.faces
            for m3Object in division.objects:
                region = division.regions[m3Object.regionIndex]
                regionVertexIndices = range(region.firstVertexIndex, region.firstVertexIndex + region.numberOfVertices)
                firstVertexIndexIndex = region.firstFaceVertexIndexIndex
                lastVertexIndexIndex = firstVertexIndexIndex + region.numberOfFaceVertexIndices
                firstVertexIndex = region.firstVertexIndex
                assert region.numberOfFaceVertexIndices % 3 == 0

                uvwMult = getattr(region, 'uvwMult', 16.0)
                uvwOffset = getattr(region, 'uvwOffset', 0.0)

                facesWithOldIndices = []  # old index = index of vertex in m3Vertices

                vertexIndexIndex = firstVertexIndexIndex
                while vertexIndexIndex + 2 <= lastVertexIndexIndex:
                    i0 = firstVertexIndex + divisionFaceIndices[vertexIndexIndex]
                    i1 = firstVertexIndex + divisionFaceIndices[vertexIndexIndex + 1]
                    i2 = firstVertexIndex + divisionFaceIndices[vertexIndexIndex + 2]
                    # some weirdness in REGNV2 from SC2 Beta
                    if region.structureDescription.structureVersion <= 2:
                        i0 -= firstVertexIndex
                        i1 -= firstVertexIndex
                        i2 -= firstVertexIndex
                    face = (i0, i1, i2)
                    facesWithOldIndices.append(face)
                    vertexIndexIndex += 3

                boneIndexLookup = model.boneLookup[region.firstBoneLookupIndex:region.firstBoneLookupIndex + region.numberOfBoneLookupIndices]
                numberOfBones = len(boneIndexLookup)
                preferedMeshName = "Mesh"
                if numberOfBones == 1:
                    preferedMeshName = self.model.bones[boneIndexLookup[0]].name
                mesh = bpy.data.meshes.new(preferedMeshName)
                meshObject = bpy.data.objects.new(preferedMeshName, mesh)
                meshObject.location = self.scene.cursor.location
                meshObject.show_name = True
                self.scene.collection.objects.link(meshObject)

                mesh.m3_material_name = self.getNameOfMaterialWithReferenceIndex(m3Object.materialReferenceIndex)

                # merge vertices together which have always the same position and normal:
                # This way there are not only fewer vertices to edit,
                # but also the calculated normals will more likly match
                # the given ones.

                # old (stored) vertex -> tuple of vertex data that makes the vertex unique
                oldVertexIndexToTupleIdMap = {}
                for vertexIndex in regionVertexIndices:
                    m3Vertex = m3Vertices[vertexIndex]
                    v = m3Vertex
                    idTuple = (v.position.x, v.position.y, v.position.z, v.boneWeight0, v.boneWeight1, v.boneWeight2, v.boneWeight3, v.boneLookupIndex0, v.boneLookupIndex1, v.boneLookupIndex2, v.boneLookupIndex3, v.normal.x, v.normal.y, v.normal.z)
                    oldVertexIndexToTupleIdMap[vertexIndex] = idTuple

                nonTrianglesCounter = 0
                tranglesWithOldIndices = []
                for face in facesWithOldIndices:
                    t0 = oldVertexIndexToTupleIdMap[face[0]]
                    t1 = oldVertexIndexToTupleIdMap[face[1]]
                    t2 = oldVertexIndexToTupleIdMap[face[2]]
                    if (t0 != t1 and t0 != t2 and t1 != t2):
                        tranglesWithOldIndices.append(face)
                    else:
                        nonTrianglesCounter += 1
                if nonTrianglesCounter > 0:
                    pass
                    # print("Warning: The mesh contained %d invalid triangles which have been ignored" % nonTrianglesCounter)

                vertexPositions = []
                vertexSign = []
                nextNewVertexIndex = 0
                oldVertexIndexToNewVertexIndexMap = {}
                newVertexIndexToOldVertexIndicesMap = {}
                vertexIdTupleToNewIndexMap = {}

                for vertexIndex in regionVertexIndices:
                    idTuple = oldVertexIndexToTupleIdMap[vertexIndex]
                    newIndex = vertexIdTupleToNewIndexMap.get(idTuple)
                    if newIndex is None:
                        newIndex = nextNewVertexIndex
                        nextNewVertexIndex += 1
                        m3Vertex = m3Vertices[vertexIndex]
                        vertexPositions.append((m3Vertex.position.x, m3Vertex.position.y, m3Vertex.position.z))
                        vertexSign.append(m3Vertex.sign)
                        vertexIdTupleToNewIndexMap[idTuple] = newIndex
                    oldVertexIndexToNewVertexIndexMap[vertexIndex] = newIndex
                    # store which old vertex indices where merged to a new one:
                    oldVertexIndices = newVertexIndexToOldVertexIndicesMap.get(newIndex)
                    if oldVertexIndices is None:
                        oldVertexIndices = set()
                        newVertexIndexToOldVertexIndicesMap[newIndex] = oldVertexIndices
                    oldVertexIndices.add(vertexIndex)

                # since vertices got merged, the indices of the faces aren't correct anymore.
                # the old face indices however are still later required to figure out
                # what Uv coordinates a face has.
                trianglesWithNewIndices = []
                for faceWithOldIndices in tranglesWithOldIndices:
                    i0 = oldVertexIndexToNewVertexIndexMap[faceWithOldIndices[0]]
                    i1 = oldVertexIndexToNewVertexIndexMap[faceWithOldIndices[1]]
                    i2 = oldVertexIndexToNewVertexIndexMap[faceWithOldIndices[2]]
                    isATriangle = ((i0 != i1) and (i1 != i2) and (i0 != i2))
                    if isATriangle:
                        faceWithNewIndices = (i0, i1, i2)
                        trianglesWithNewIndices.append(faceWithNewIndices)

                mesh.vertices.add(len(vertexPositions))
                mesh.vertices.foreach_set("co", io_utils.unpack_list(vertexPositions))

                triangleCount = len(trianglesWithNewIndices)
                mesh.polygons.add(triangleCount)
                mesh.loops.add(triangleCount * 3)
                mesh.polygons.foreach_set("loop_start", range(0, triangleCount * 3, 3))
                mesh.polygons.foreach_set("loop_total", (3,) * triangleCount)
                mesh.loops.foreach_set("vertex_index", io_utils.unpack_list(trianglesWithNewIndices))

                for vertexUVAttribute in ["uv0", "uv1", "uv2", "uv3"]:
                    if vertexStructureDescription.hasField(vertexUVAttribute):
                        uvLayer = mesh.uv_layers.new()
                        for faceIndex, polygon in enumerate(mesh.polygons):
                            oldIndices = tranglesWithOldIndices[faceIndex]
                            for i in range(3):
                                uvLayer.data[polygon.loop_start + i].uv = toBlenderUVCoordinate(
                                    getattr(m3Vertices[oldIndices[i]], vertexUVAttribute),
                                    uvwMult,
                                    uvwOffset
                                )

                mesh.validate()
                mesh.update(calc_edges=True)

                if self.boneNames is not None:
                    vertexGroupLookup = []
                    for boneIndex in boneIndexLookup:
                        boneName = self.boneNames[boneIndex]
                        if boneName in meshObject.vertex_groups:
                            vertexGroup = meshObject.vertex_groups[boneName]
                        else:
                            vertexGroup = meshObject.vertex_groups.new(name=boneName)
                        vertexGroupLookup.append(vertexGroup)
                    for vertexIndex in range(region.firstVertexIndex, region.firstVertexIndex + region.numberOfVertices):
                        m3Vertex = m3Vertices[vertexIndex]
                        boneWeightsAsInt = [m3Vertex.boneWeight0, m3Vertex.boneWeight1, m3Vertex.boneWeight2, m3Vertex.boneWeight3]
                        boneLookupIndices = [m3Vertex.boneLookupIndex0, m3Vertex.boneLookupIndex1, m3Vertex.boneLookupIndex2, m3Vertex.boneLookupIndex3]
                        for boneWeightAsInt, boneLookupIndex in zip(boneWeightsAsInt, boneLookupIndices):
                            if boneWeightAsInt != 0:
                                vertexGroup = vertexGroupLookup[boneLookupIndex]
                                boneWeight = boneWeightAsInt / 255.0
                                vertexGroup.add([oldVertexIndexToNewVertexIndexMap[vertexIndex]], boneWeight, 'REPLACE')

                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.select_all(action='DESELECT')
                self.scene.view_layers[0].objects.active = meshObject
                meshObject.select_set(True)
                bpy.ops.object.mode_set(mode='EDIT')

                bm = bmesh.from_edit_mesh(mesh)
                layer = bm.faces.layers.int.new("m3sign")
                for face in bm.faces:
                    for vert in face.verts:
                        if vertexSign[vert.index] == 1.0:
                            face[layer] = 1
                            break

                # Need to set mode back to object so that bmesh is cleared and does not interfere with the rest of the operations
                bpy.ops.object.mode_set(mode='OBJECT')

                if self.scene.m3_import_options.applySmoothShading:
                    for polygon in mesh.polygons:
                        polygon.use_smooth = True

                if self.scene.m3_import_options.markSharpEdges:
                    self.markBordersEdgesSharp(mesh)
                    # Remove doubles after marking the sharp edges
                    # since the sharp edge detection algrithm depend on it
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.remove_doubles()

                self.setOriginToCenter(meshObject)

                if self.armatureObject is not None:
                    modifier = meshObject.modifiers.new('UseArmature', 'ARMATURE')
                    modifier.object = self.armatureObject
                    modifier.use_bone_envelopes = False
                    modifier.use_vertex_groups = True

                if self.scene.m3_import_options.markSharpEdges:
                    modifier = meshObject.modifiers.new('EdgeSplit', 'EDGE_SPLIT')
                    modifier.use_edge_angle = False

                if self.scene.m3_import_options.generateBlenderMaterials:
                    shared.createBlenderMaterialForMeshObject(self.scene, meshObject)

    def setOriginToCenter(self, meshObject):
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        self.scene.view_layers[0].objects.active = meshObject
        meshObject.select_set(True)
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')

    def markBordersEdgesSharp(self, mesh):

        allPolygonEdges = []

        for polygon in mesh.polygons:
            if polygon.vertices[0] < polygon.vertices[1]:
                edge0 = (polygon.vertices[0], polygon.vertices[1])
            else:
                edge0 = (polygon.vertices[1], polygon.vertices[0])
            if polygon.vertices[1] < polygon.vertices[2]:
                edge1 = (polygon.vertices[1], polygon.vertices[2])
            else:
                edge1 = (polygon.vertices[2], polygon.vertices[1])
            if polygon.vertices[2] < polygon.vertices[0]:
                edge2 = (polygon.vertices[2], polygon.vertices[0])
            else:
                edge2 = (polygon.vertices[0], polygon.vertices[2])
            allPolygonEdges.append(edge0)
            allPolygonEdges.append(edge1)
            allPolygonEdges.append(edge2)
        uniqueEdges = set()
        visitedEdges = set()
        for edge in allPolygonEdges:
            if edge in visitedEdges:
                if edge in uniqueEdges:
                    uniqueEdges.remove(edge)
            else:
                visitedEdges.add(edge)
                uniqueEdges.add(edge)

        for edgeObject in mesh.edges:
            if edgeObject.vertices[0] < edgeObject.vertices[1]:
                edge = (edgeObject.vertices[0], edgeObject.vertices[1])
            else:
                edge = (edgeObject.vertices[1], edgeObject.vertices[0])
            if edge in uniqueEdges:
                edgeObject.use_edge_sharp = True
        # mesh.show_edge_sharp = True

    def determineRelEditBoneMatrices(self, m3Bones, editBones):
        absEditBoneMatrices = []
        relEditBoneMatrices = []
        for boneEntry, editBone in zip(m3Bones, editBones):
            absEditBoneMatrix = editBone.matrix
            absEditBoneMatrices.append(absEditBoneMatrix)
            if boneEntry.parent != -1:
                parentEditBone = editBones[boneEntry.parent]
                absParentEditBoneMatrix = parentEditBone.matrix
                relEditBoneMatrix = absParentEditBoneMatrix.inverted() @ absEditBoneMatrix
            else:
                relEditBoneMatrix = absEditBoneMatrix
            relEditBoneMatrices.append(relEditBoneMatrix)
        return relEditBoneMatrices

    def determineBoneNameList(self, m3Bones):
        uniqueNameFinder = shared.UniqueNameFinder()
        for currentObject in self.scene.objects:
            if currentObject.type == 'ARMATURE':
                armatureObject = currentObject
                armature = armatureObject.data
                uniqueNameFinder.markNamesOfCollectionAsUsed(armature.bones)

        names = []
        for m3Bone in m3Bones:
            wantedName = m3Bone.name
            name = uniqueNameFinder.findNameAndMarkAsUsedLike(wantedName)
            names.append(name)

        return names

    def createEditBones(self, m3Bones, heads, tails, rolls, bindScales):

        for m3Bone in m3Bones:
            self.boneNames.append(m3Bone.name)

        editBones = []
        for index, boneEntry in enumerate(m3Bones):
            editBone = self.armature.edit_bones.new(self.boneNames[index])
            editBone.head = heads[index]
            editBone.tail = tails[index]
            editBone.roll = rolls[index]

            if boneEntry.parent != -1:
                parentEditBone = editBones[boneEntry.parent]
                editBone.parent = parentEditBone
                parentToChildVector = parentEditBone.tail - editBone.head

                animId = boneEntry.location.header.animId
                if parentToChildVector.length < 0.000001:
                    animated = False
                    for animIdSet in self.sequenceNameAndSTCIndexToAnimIdSet.values():
                        if animId in animIdSet:
                            animated = True
                    if not animated:
                        editBone.use_connect = True

            editBone.m3_bind_scale = bindScales[index]
            editBones.append(editBone)
        return editBones

    def createAnimIdToKeyFramesMapFor(self, stc):
        keyFramesLists = [stc.sdev, stc.sd2v, stc.sd3v, stc.sd4q, stc.sdcc, stc.sdr3, stc.unknownRef8, stc.sds6, stc.sdu6, stc.unknownRef11, stc.sdu3, stc.sdfg, stc.sdmb]
        animIdToTimeValueMap = {}
        for i in range(len(stc.animIds)):
            animId = stc.animIds[i]
            animRef = stc.animRefs[i]
            animType = animRef >> 16
            animIndex = animRef & 0xffff
            keyFramesList = keyFramesLists[animType]
            keyFramesEntry = keyFramesList[animIndex]

            timeEntries = keyFramesEntry.frames
            valueEntries = keyFramesEntry.keys
            timeValueMap = {}
            for timeEntry, valueEntry in zip(timeEntries, valueEntries):
                timeValueMap[timeEntry] = valueEntry

            animIdToTimeValueMap[animId] = timeValueMap

        return animIdToTimeValueMap

    def createOrGetActionFor(self, ob, animationTempData):
        scene = bpy.context.scene
        animation = scene.m3_animations[animationTempData.animationIndex]

        if ob.animation_data is None:
            ob.animation_data_create()

        actionName = ob.name + animation.name
        action = bpy.data.actions[actionName] if actionName in bpy.data.actions else bpy.data.actions.new(actionName)
        action.use_fake_user = True
        action.id_root = shared.typeIdOfObject(ob)

        return action

    def createAnimations(self):
        # print("Creating actions(animation sequences)")
        scene = bpy.context.scene
        model = self.model
        numberOfSequences = len(model.sequences)
        if len(model.sequenceTransformationGroups) != numberOfSequences:
            raise Exception("The model has not the same amounth of stg elements as it has sequences")

        uniqueNameFinder = shared.UniqueNameFinder()
        uniqueNameFinder.markNamesOfCollectionAsUsed(self.scene.m3_animations)

        self.sequenceNameAndSTCIndexToAnimIdSet = {}
        for sequenceIndex in range(numberOfSequences):
            sequence = model.sequences[sequenceIndex]
            stg = model.sequenceTransformationGroups[sequenceIndex]
            if (sequence.name != stg.name):
                raise Exception("Name of sequence and it's transformation group does not match")
            animationIndex = len(scene.m3_animations)
            animation = scene.m3_animations.add()
            transferer = M3ToBlenderDataTransferer(self, None, None, blenderObject=animation, m3Object=sequence)
            shared.transferAnimation(transferer)

            animation.nameOld = animation.name
            animation.name = uniqueNameFinder.findNameAndMarkAsUsedLike(sequence.name)
            animation.startFrame = msToFrame(sequence.animStartInMS)
            animation.exlusiveEndFrame = msToFrame(sequence.animEndInMS)

            animIdToTimeValueMap = {}
            for m3STCIndex in stg.stcIndices:
                stc = model.sequenceTransformationCollections[m3STCIndex]
                animationSTCIndex = transformationCollection = len(animation.transformationCollections)
                transformationCollection = animation.transformationCollections.add()
                transformationCollectionName = stc.name
                stcPrefix = sequence.name + "_"
                if transformationCollectionName.startswith(stcPrefix):
                    transformationCollectionName = transformationCollectionName[len(stcPrefix):]

                transformationCollection.name = transformationCollectionName

                transferer = M3ToBlenderDataTransferer(self, None, None, blenderObject=transformationCollection, m3Object=stc)
                shared.transferSTC(transferer)
                animIdsOfSTC = set()
                animIdToTimeValueMapForSTC = self.createAnimIdToKeyFramesMapFor(stc)
                for animId, timeValueMap in animIdToTimeValueMapForSTC.items():
                    if animId in animIdToTimeValueMap:
                        raise Exception("Same animid %s got animated by different STC" % animId)
                    animIdToTimeValueMap[animId] = timeValueMap
                    animIdsOfSTC.add(animId)

                self.sequenceNameAndSTCIndexToAnimIdSet[sequence.name, animationSTCIndex] = animIdsOfSTC

                # stc.seqIndex seems to be wrong:
                # sequence = model.sequences[stc.seqIndex]
                if len(stc.animIds) != len(stc.animRefs):
                    raise Exception("len(stc.animids) != len(stc.animrefs)")

                # Find simulate frame
                for currSdev in stc.sdev:
                    evtSimulate = [*filter(lambda x: x.name == 'Evt_Simulate', currSdev.keys)]
                    if len(evtSimulate) > 0:
                        assert len(evtSimulate) == 1  # there should be just one match for this event
                        animation.useSimulateFrame = True
                        animation.simulateFrame = msToFrame(currSdev.frames[0])

            self.animations.append(AnimationTempData(animIdToTimeValueMap, animationIndex))

    def initSTCsOfAnimations(self):
        unsupportedAnimIds = set()
        for sequenceNameAndSTCIndex, animIds in self.sequenceNameAndSTCIndexToAnimIdSet.items():
            sequenceName, stcIndex = sequenceNameAndSTCIndex
            stc = self.scene.m3_animations[sequenceName].transformationCollections[stcIndex]
            for animId in animIds:
                longAnimId = self.animIdToLongAnimIdMap.get(animId)
                if longAnimId is not None:
                    animatedProperty = stc.animatedProperties.add()
                    animatedProperty.longAnimId = longAnimId
                else:
                    unsupportedAnimIds.add(animId)
        animationEndEventAnimId = 0x65bd3215
        if animationEndEventAnimId in unsupportedAnimIds:
            unsupportedAnimIds.remove(animationEndEventAnimId)
        # else:
        #     print("Warning: Model contained no animation with animId %d which are usually used for marking the end of an animation" % animationEndEventAnimId)

        if len(unsupportedAnimIds) > 0:
            animIdToPathMap = {}
            self.addAnimIdPathToMap("model", self.model, animIdToPathMap)
            for unsupportedAnimId in unsupportedAnimIds:
                path = animIdToPathMap.get(unsupportedAnimId, "<unknown path>")
                # print("Warning: Ignoring unsupported animated property with animId %s and path %s" % (hex(unsupportedAnimId), path))

    def addAnimIdPathToMap(self, path, m3Object, animIdToPathMap):
        if hasattr(m3Object, "header") and type(m3Object.header) == m3.AnimationReferenceHeader:
            header = m3Object.header
            if header.animFlags == shared.animFlagsForAnimatedProperty:
                animIdToPathMap[header.animId] = path
        if hasattr(type(m3Object), "fields"):
            for fieldName in m3Object.fields:
                fieldValue = getattr(m3Object, fieldName)
                if fieldValue is None:
                    pass
                elif fieldValue.__class__ == list:
                    for entryIndex, entry in enumerate(fieldValue):
                        entryPath = "%s.%s[%d]" % (path, fieldName, entryIndex)
                        self.addAnimIdPathToMap(entryPath, entry, animIdToPathMap)
                else:
                    fieldPath = path + "." + fieldName
                    self.addAnimIdPathToMap(fieldPath, fieldValue, animIdToPathMap)

    def actionAndTimeValueMapPairsFor(self, animId):
        for animationTempData in self.animations:
            timeValueMap = animationTempData.animIdToTimeValueMap.get(animId)
            if timeValueMap is not None:
                action = self.createOrGetActionFor(self.scene, animationTempData)
                yield (action, timeValueMap)

    def animateFloat(self, objectWithAnimationData, path, animId, defaultValue):
        # TODO let animateFloat take objectId as argument
        defaultAction = shared.getOrCreateDefaultActionFor(objectWithAnimationData)
        shared.setDefaultValue(defaultAction, path, 0, defaultValue)

        self.addAnimIdData(animId, objectId=shared.animObjectIdScene, animPath=path)
        for action, timeValueMap in self.actionAndTimeValueMapPairsFor(animId):
            curve = action.fcurves.new(path, index=0)
            for frame, value in frameValuePairs(timeValueMap):
                insertLinearKeyFrame(curve, frame, value)

    def animateInteger(self, objectWithAnimationData, pathPrefix, field, animId, defaultValue):
        defaultAction = shared.getOrCreateDefaultActionFor(objectWithAnimationData)
        path = pathPrefix + field
        shared.setDefaultValue(defaultAction, path, 0, defaultValue)
        self.addAnimIdData(animId, objectId=shared.animObjectIdScene, animPath=path)
        if field == "partEmit":
            for action, timeValueMap in self.actionAndTimeValueMapPairsFor(animId):
                curve = action.fcurves.new(path, index=0)
                for frame, value in frameValuePairs(timeValueMap):
                    insertConstantKeyFrame(curve, frame, value)
                    if value != 0:
                        insertConstantKeyFrame(curve, frame + 1, 0)
        else:
            for action, timeValueMap in self.actionAndTimeValueMapPairsFor(animId):
                curve = action.fcurves.new(path, index=0)
                for frame, value in frameValuePairs(timeValueMap):
                    insertConstantKeyFrame(curve, frame, value)

    def animateVector3(self, objectWithAnimationData, path, animId, defaultValue):
        defaultAction = shared.getOrCreateDefaultActionFor(objectWithAnimationData)
        shared.setDefaultValue(defaultAction, path, 0, defaultValue.x)
        shared.setDefaultValue(defaultAction, path, 1, defaultValue.y)
        shared.setDefaultValue(defaultAction, path, 2, defaultValue.z)

        self.addAnimIdData(animId, objectId=shared.animObjectIdScene, animPath=path)
        for action, timeValueMap in self.actionAndTimeValueMapPairsFor(animId):
            xCurve = action.fcurves.new(path, index=0)
            yCurve = action.fcurves.new(path, index=1)
            zCurve = action.fcurves.new(path, index=2)

            for frame, value in frameValuePairs(timeValueMap):
                insertLinearKeyFrame(xCurve, frame, value.x)
                insertLinearKeyFrame(yCurve, frame, value.y)
                insertLinearKeyFrame(zCurve, frame, value.z)

    def animateVector2(self, objectWithAnimationData, path, animId, defaultValue):
        defaultAction = shared.getOrCreateDefaultActionFor(objectWithAnimationData)
        shared.setDefaultValue(defaultAction, path, 0, defaultValue.x)
        shared.setDefaultValue(defaultAction, path, 0, defaultValue.y)

        self.addAnimIdData(animId, objectId=shared.animObjectIdScene, animPath=path)
        for action, timeValueMap in self.actionAndTimeValueMapPairsFor(animId):
            xCurve = action.fcurves.new(path, index=0)
            yCurve = action.fcurves.new(path, index=1)

            for frame, value in frameValuePairs(timeValueMap):
                insertLinearKeyFrame(xCurve, frame, value.x)
                insertLinearKeyFrame(yCurve, frame, value.y)

    def animateColor(self, objectWithAnimationData, path, animId, m3DefaultValue):
        defaultAction = shared.getOrCreateDefaultActionFor(objectWithAnimationData)
        defaultValue = toBlenderColorVector(m3DefaultValue)
        for i in range(4):
            shared.setDefaultValue(defaultAction, path, i, defaultValue[i])

        self.addAnimIdData(animId, objectId=shared.animObjectIdScene, animPath=path)
        for action, timeValueMap in self.actionAndTimeValueMapPairsFor(animId):
            redCurve = action.fcurves.new(path, index=0)
            greenCurve = action.fcurves.new(path, index=1)
            blueCurve = action.fcurves.new(path, index=2)
            alphaCurve = action.fcurves.new(path, index=3)

            for frame, value in frameValuePairs(timeValueMap):
                v = toBlenderColorVector(value)
                insertLinearKeyFrame(redCurve, frame, v[0])
                insertLinearKeyFrame(greenCurve, frame, v[1])
                insertLinearKeyFrame(blueCurve, frame, v[2])
                insertLinearKeyFrame(alphaCurve, frame, v[3])

    def animateBoundings(self, objectWithAnimationData, animPathMinBorder, animPathMaxBorder, animPathRadius, animId, minBorderDefault, maxBorderDefault, radiusDefault):
        # Store default values in an action:
        defaultAction = shared.getOrCreateDefaultActionFor(objectWithAnimationData)
        for i in range(3):
            shared.setDefaultValue(defaultAction, animPathMinBorder, i, minBorderDefault[i])

        for i in range(3):
            shared.setDefaultValue(defaultAction, animPathMaxBorder, i, maxBorderDefault[i])

        shared.setDefaultValue(defaultAction, animPathRadius, 0, radiusDefault)

        # Which path we pass to addAnimIdData does not matter,
        # since they all would result in the same longAnimId (see getLongAnimIdOf):
        self.addAnimIdData(animId, objectId=shared.animObjectIdScene, animPath=animPathMinBorder)
        for action, timeValueMap in self.actionAndTimeValueMapPairsFor(animId):
            minXCurve = action.fcurves.new(animPathMinBorder, index=0)
            minYCurve = action.fcurves.new(animPathMinBorder, index=1)
            minZCurve = action.fcurves.new(animPathMinBorder, index=2)
            maxXCurve = action.fcurves.new(animPathMaxBorder, index=0)
            maxYCurve = action.fcurves.new(animPathMaxBorder, index=1)
            maxZCurve = action.fcurves.new(animPathMaxBorder, index=2)
            radiusCurve = action.fcurves.new(animPathRadius, index=0)

            for frame, value in frameValuePairs(timeValueMap):
                insertLinearKeyFrame(minXCurve, frame, value.minBorder.x)
                insertLinearKeyFrame(minYCurve, frame, value.minBorder.y)
                insertLinearKeyFrame(minZCurve, frame, value.minBorder.z)
                insertLinearKeyFrame(maxXCurve, frame, value.maxBorder.x)
                insertLinearKeyFrame(maxYCurve, frame, value.maxBorder.y)
                insertLinearKeyFrame(maxZCurve, frame, value.maxBorder.z)
                insertLinearKeyFrame(radiusCurve, frame, value.radius)


def boneRotMatrix(head, tail, roll):
    """unused: python port of the Blender C Function vec_roll_to_mat3 """
    v = tail - head
    v.normalize()
    target = mathutils.Vector((0, 1, 0))
    axis = target.cross(v)
    if axis.dot(axis) > 0.000001:
        axis.normalize()
        theta = target.angle(v)
        bMatrix = mathutils.Matrix.Rotation(theta, 3, axis)
    else:
        if target.dot(v) > 0:
            updown = 1.0
        else:
            updown = -1.0

        bMatrix = mathutils.Matrix((
            (updown, 0, 0),
            (0, updown, 0),
            (0, 0, 1)))

    rMatrix = mathutils.Matrix.Rotation(roll, 3, v)
    return rMatrix @ bMatrix


def boneMatrix(head, tail, roll):
    """unused: how blender calculates the matrix of a bone """
    rotMatrix = boneRotMatrix(head, tail, roll)
    matrix = rotMatrix.to_4x4()
    matrix.translation = head
    return matrix


def importM3BasedOnM3ImportOptions(scene):
    importer = Importer()
    importer.importM3BasedOnM3ImportOptions(scene)
