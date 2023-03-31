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

from typing import Iterable, List, Dict
from . import m3
from . import shared
from .shared import ExportError
from . import cm
from .common import mlog
import bpy
import mathutils
import os.path
import time
import math

actionTypeScene = "SCENE"
actionTypeArmature = "OBJECT"


class ExportErrorMODLVersionInsufficient(ExportError):
    def __init__(self, minVersion: int, cause: str = None):
        super().__init__(f'Unable to export in choosen version of m3 container, try version {minVersion} or higher. Reason: {cause}.')


class Exporter:
    def __init__(self, scene: bpy.types.Scene, operator: bpy.types.Operator):
        self.scene = scene
        self.operator = operator

    def export(self, m3FileName):
        self.initStructureVersionMap()
        self.selectAnimationsForExport()
        self.isAnimationExport = m3FileName.endswith(".m3a")
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')
        self.generatedAnimIdCounter = 0
        self.boundingAnimId = 0x1f9bd2
        if self.scene.render.fps != 30:
            print("Warning: The currently configured frame rate is %s. For compability the model will be exported with a frame rate of 30." % self.scene.render.fps)
        self.boneIndexToDefaultAbsoluteMatrixMap = {}
        self.animationNameToFrameToBoneIndexToAbsoluteMatrixMap = {}
        self.prepareAnimIdMaps()
        self.nameToAnimIdToAnimDataMap = {}
        self.restPositionsOfExportedBones = []
        for animationIndex in self.animationIndicesToExport:
            animation = self.scene.m3_animations[animationIndex]
            if animation.name in self.nameToAnimIdToAnimDataMap:
                raise ExportError("Animations must have unique names. Use number suffixes like 'Stand 01' and 'Stand 02'")
            self.nameToAnimIdToAnimDataMap[animation.name] = {}
        self.initOldReferenceIndicesInCorrectedOrder()
        self.initMaterialNameToNewReferenceIndexMap()

        model = self.createModel(m3FileName)
        m3.saveAndInvalidateModel(model, m3FileName)

    def initStructureVersionMap(self):
        self.structureVersionMap = {}
        if self.scene.m3_export_options.modlVersion == "29":
            self.structureVersionMap["MODL"] = 29
            self.structureVersionMap["EVNT"] = 2
            self.structureVersionMap["SEQS"] = 2
            self.structureVersionMap["LAYR"] = 26
            self.structureVersionMap["MAT_"] = 20
            self.structureVersionMap["PAR_"] = 24
            self.structureVersionMap["PROJ"] = 5
            self.structureVersionMap["PHSH"] = 3
            self.structureVersionMap["PHRB"] = 4
            self.structureVersionMap["RIB_"] = 9
        elif self.scene.m3_export_options.modlVersion == "26":
            self.structureVersionMap["MODL"] = 26
            self.structureVersionMap["EVNT"] = 2
            self.structureVersionMap["SEQS"] = 2
            self.structureVersionMap["LAYR"] = 25
            self.structureVersionMap["MAT_"] = 18
            self.structureVersionMap["PAR_"] = 23
            self.structureVersionMap["PROJ"] = 5
            self.structureVersionMap["PHSH"] = 3
            self.structureVersionMap["PHRB"] = 4
            self.structureVersionMap["RIB_"] = 8
        elif self.scene.m3_export_options.modlVersion == "23":
            self.structureVersionMap["MODL"] = 23
            self.structureVersionMap["EVNT"] = 1
            self.structureVersionMap["SEQS"] = 1
            self.structureVersionMap["LAYR"] = 22
            self.structureVersionMap["MAT_"] = 15
            self.structureVersionMap["PAR_"] = 12
            self.structureVersionMap["PROJ"] = 4
            self.structureVersionMap["PHSH"] = 1
            self.structureVersionMap["PHRB"] = 2
            self.structureVersionMap["RIB_"] = 6
        else:
            raise ExportError('Unsupported M3 container: V%s' % self.scene.m3_export_options.modlVersion)

        self.structureVersionMap["BONE"] = 1
        self.structureVersionMap["Vector3AnimationReference"] = 0
        self.structureVersionMap["QuaternionAnimationReference"] = 0
        self.structureVersionMap["SD3V"] = 0
        self.structureVersionMap["SD4Q"] = 0
        self.structureVersionMap["SD3V"] = 0
        self.structureVersionMap["SDEV"] = 0
        self.structureVersionMap["SDU6"] = 0
        self.structureVersionMap["VertexFormat0x182027d"] = 0
        self.structureVersionMap["VertexFormat0x182007d"] = 0
        self.structureVersionMap["VertexFormat0x186007d"] = 0
        self.structureVersionMap["VertexFormat0x186027d"] = 0
        self.structureVersionMap["VertexFormat0x18e007d"] = 0
        self.structureVersionMap["VertexFormat0x19e007d"] = 0
        self.structureVersionMap["DIV_"] = 2
        self.structureVersionMap["REGN"] = 3
        self.structureVersionMap["BAT_"] = 1
        self.structureVersionMap["Vector3As3Fixed8"] = 0
        self.structureVersionMap["Vector2As2int16"] = 0
        self.structureVersionMap["STG_"] = 0
        self.structureVersionMap["STC_"] = 4
        self.structureVersionMap["STS_"] = 0
        self.structureVersionMap["CAM_"] = 3
        self.structureVersionMap["SSGS"] = 1
        self.structureVersionMap["PARC"] = 0
        self.structureVersionMap["FOR_"] = 1
        self.structureVersionMap["LITE"] = 7
        self.structureVersionMap["BBSC"] = 0
        self.structureVersionMap["ATT_"] = 1
        self.structureVersionMap["ATVL"] = 0
        self.structureVersionMap["COL"] = 0
        self.structureVersionMap["Matrix44"] = 0
        self.structureVersionMap["IREF"] = 0
        self.structureVersionMap["DIS_"] = 4
        self.structureVersionMap["CMP_"] = 2
        self.structureVersionMap["CMS_"] = 0
        self.structureVersionMap["TER_"] = 0
        self.structureVersionMap["VOL_"] = 0
        self.structureVersionMap["CREP"] = 0
        self.structureVersionMap["VON_"] = 0
        self.structureVersionMap["Vector2AnimationReference"] = 0
        self.structureVersionMap["Int16AnimationReference"] = 0
        self.structureVersionMap["UInt16AnimationReference"] = 0
        self.structureVersionMap["UInt32AnimationReference"] = 0
        self.structureVersionMap["FloatAnimationReference"] = 0
        self.structureVersionMap["AnimationReferenceHeader"] = 0
        self.structureVersionMap["MATM"] = 0
        self.structureVersionMap["MSEC"] = 1
        self.structureVersionMap["BNDSV0AnimationReference"] = 0
        self.structureVersionMap["BNDS"] = 0
        self.structureVersionMap["VEC4"] = 0
        self.structureVersionMap["QUAT"] = 0
        self.structureVersionMap["VEC3"] = 0
        self.structureVersionMap["VEC2"] = 0
        self.structureVersionMap["ColorAnimationReference"] = 0
        self.structureVersionMap["SDCC"] = 0
        self.structureVersionMap["SDR3"] = 0
        self.structureVersionMap["SDS6"] = 0
        self.structureVersionMap["FLAG"] = 0
        self.structureVersionMap["SDMB"] = 0
        self.structureVersionMap["SD2V"] = 0
        self.structureVersionMap["FlagAnimationReference"] = 0
        self.structureVersionMap["SVC3"] = 0
        self.structureVersionMap["WRP_"] = 1
        self.structureVersionMap["SRIB"] = 0
        self.structureVersionMap["STBM"] = 0
        self.structureVersionMap["SDFG"] = 0
        self.structureVersionMap["SDU3"] = 0
        self.structureVersionMap["IKJT"] = 0
        self.structureVersionMap["TRGD"] = 0
        self.structureVersionMap["PATU"] = 4
        self.structureVersionMap["PHYJ"] = 0

    def getVersionOf(self, structureName):
        return self.structureVersionMap[structureName]

    def createInstanceOf(self, structureName):
        version = self.structureVersionMap[structureName]
        structureDescription = m3.structures[structureName].getVersion(version)
        return structureDescription.createInstance()

    def selectAnimationsForExport(self):
        scene = self.scene
        animationExportAmount = scene.m3_export_options.animationExportAmount
        if animationExportAmount == shared.exportAmountAllAnimations:
            self.animationIndicesToExport = range(len(scene.m3_animations))
        elif animationExportAmount == shared.exportAmountCurrentAnimation:
            self.animationIndicesToExport = [scene.m3_animation_index]
        elif animationExportAmount == shared.exportAmountNoAnimations:
            self.animationIndicesToExport = []
        else:
            raise ExportError("Unsupported export amount option: %s" % scene.m3_export_options)

    def createModel(self, m3FileName):
        model = self.createInstanceOf("MODL")
        model.modelName = os.path.basename(m3FileName)

        self.initBones(model)
        self.initMesh(model)
        self.initMaterials(model)
        self.initCameras(model)
        self.initFuzzyHitTests(model)
        self.initTighHitTest(model)
        self.initParticles(model)
        self.initRibbons(model)
        self.initProjections(model)
        self.initWarps(model)
        self.initForces(model)
        self.initRigidBodies(model)
        self.initLights(model)
        self.initBillboardBehaviors(model)
        self.initIkChains(model)
        self.initTurretBehaviors(model)
        self.initPhysicsJoints(model)
        self.initVisibilityTest(model)
        # TODO remove call and method:
        # self.initBoundings(model)
        self.initAttachmentPoints(model)
        self.prepareAnimationEndEvents()
        self.initWithPreparedAnimationData(model)
        model.uniqueUnknownNumber = self.getAnimIdFor(shared.animObjectIdModel, "")
        self.updateAnimationIdsOfBlendFile()
        return model

    def prepareAnimIdMaps(self):
        self.longAnimIdToAnimIdMap = {}
        self.usedAnimIds = {self.boundingAnimId}

        for animIdData in self.scene.m3_animation_ids:
            animId = animIdData.animIdMinus2147483648 + 2147483648
            longAnimId = animIdData.longAnimId
            self.longAnimIdToAnimIdMap[longAnimId] = animId
            self.usedAnimIds.add(animId)

    def getAnimIdForLongAnimId(self, longAnimId):
        animId = self.longAnimIdToAnimIdMap.get(longAnimId)
        if animId is None:
            animId = shared.getRandomAnimIdNotIn(self.usedAnimIds)
            self.usedAnimIds.add(animId)
            self.longAnimIdToAnimIdMap[longAnimId] = animId
        return animId

    def updateAnimationIdsOfBlendFile(self):
        self.scene.m3_animation_ids.clear()
        for longAnimId, animId in self.longAnimIdToAnimIdMap.items():
            if animId in self.usedAnimIds:
                animIdData = self.scene.m3_animation_ids.add()
                animIdData.animIdMinus2147483648 = animId - 2147483648
                animIdData.longAnimId = longAnimId

    def getAnimIdFor(self, objectId, animPath):
        longAnimId = shared.getLongAnimIdOf(objectId, animPath)
        return self.getAnimIdForLongAnimId(longAnimId)

    def createUniqueAnimId(self):
        self.generatedAnimIdCounter += 1  # increase first since we don't want to use 0 as animation id
        return self.generatedAnimIdCounter

    def initBones(self, model):
        self.boneNameToDefaultPoseMatrixMap = {}
        self.boneNameToM3SpaceDefaultLocationMap = {}
        self.boneNameToM3SpaceDefaultRotationMap = {}
        self.boneNameToM3SpaceDefaultScaleMap = {}
        self.boneNameToLeftCorrectionMatrix = {}
        self.boneNameToRightCorrectionMatrix = {}
        self.boneNameToBoneIndexMap = {}  # map: bone name to index in model bone list
        boneNameToAbsInvRestPoseMatrix = {}
        self.boneIndexToAbsoluteInverseRestPoseMatrixFixedMap = {}
        self.armatureObjectNameToBoneNamesMap: Dict[str, bpy.types.Object] = {}

        # Place all bones at the default position by selecting no animation:
        self.scene.m3_animation_index = -1
        self.scene.frame_set(0)

        for armatureObject in self.findArmatureObjects():
            armature = armatureObject.data
            objectToWorldMatrix = armatureObject.matrix_world

            boneNamesOfArmature = list()
            self.armatureObjectNameToBoneNamesMap[armatureObject.name] = boneNamesOfArmature
            for blenderBoneIndex, blenderBone in enumerate(armature.bones):
                boneIndex = len(model.bones)
                boneName = blenderBone.name
                if boneName in self.boneNameToBoneIndexMap:
                    raise ExportError("There are multiple bones with the name %s" % blenderBone.name)
                boneNamesOfArmature.append(boneName)
                self.boneNameToBoneIndexMap[boneName] = boneIndex

                locationAnimPath = 'pose.bones["%s"].location' % boneName
                rotationAnimPath = 'pose.bones["%s"].rotation_quaternion' % boneName
                scaleAnimPath = 'pose.bones["%s"].scale' % boneName

                locationAnimId = self.getAnimIdFor(shared.animObjectIdArmature, locationAnimPath)
                rotationAnimId = self.getAnimIdFor(shared.animObjectIdArmature, rotationAnimPath)
                scaleAnimId = self.getAnimIdFor(shared.animObjectIdArmature, scaleAnimPath)

                bone = self.createInstanceOf("BONE")
                bone.name = boneName
                bone.flags = 0
                bone.setNamedBit("flags", "real", True)
                bone.location = self.createInstanceOf("Vector3AnimationReference")
                bone.location.header = self.createNullAnimHeader(animId=locationAnimId, interpolationType=1)
                bone.rotation = self.createInstanceOf("QuaternionAnimationReference")
                bone.rotation.header = self.createNullAnimHeader(animId=rotationAnimId, interpolationType=1)
                bone.scale = self.createInstanceOf("Vector3AnimationReference")
                bone.scale.header = self.createNullAnimHeader(animId=scaleAnimId, interpolationType=1)
                bone.ar1 = self.createNullUInt32AnimationReference(1)
                model.bones.append(bone)
                absRestPosMatrix = objectToWorldMatrix @ blenderBone.matrix_local
                self.restPositionsOfExportedBones.append(absRestPosMatrix.translation.copy())
                if not blenderBone.use_inherit_rotation:
                    raise ExportError("The setting inhertRotation=false of bone %s is not exportable!" % boneName)
                if not blenderBone.use_inherit_scale:
                    raise ExportError("The setting inhertScale=false of bone %s is not exportable!" % boneName)

                if blenderBone.parent is not None:
                    bone.parent = self.boneNameToBoneIndexMap[blenderBone.parent.name]
                    absInvRestPoseMatrixParent = boneNameToAbsInvRestPoseMatrix[blenderBone.parent.name]
                    relRestPosMatrix = absInvRestPoseMatrixParent @ absRestPosMatrix
                else:
                    bone.parent = -1
                    relRestPosMatrix = absRestPosMatrix

                poseBone: bpy.types.Bone = armatureObject.pose.bones[boneName]
                poseMatrix = armatureObject.convert_space(
                    pose_bone=poseBone,
                    matrix=poseBone.matrix,
                    from_space='POSE',
                    to_space='LOCAL',
                )

                bindScaleInverted = mathutils.Vector((1.0 / blenderBone.m3_bind_scale[i] for i in range(3)))
                bindScaleMatrixInverted = shared.scaleVectorToMatrix(bindScaleInverted)

                if blenderBone.parent is not None:
                    parentBindMatrix = shared.scaleVectorToMatrix(blenderBone.parent.m3_bind_scale)
                    leftCorrectionMatrix = parentBindMatrix @ shared.rotFixMatrix @ relRestPosMatrix
                else:
                    leftCorrectionMatrix = relRestPosMatrix

                rightCorrectionMatrix = shared.rotFixMatrixInverted @ bindScaleMatrixInverted
                m3PoseMatrix = leftCorrectionMatrix @ poseMatrix @ rightCorrectionMatrix

                self.boneNameToLeftCorrectionMatrix[boneName] = leftCorrectionMatrix
                self.boneNameToRightCorrectionMatrix[boneName] = rightCorrectionMatrix

                m3SpaceLocation, m3SpaceRotation, m3SpaceScale = m3PoseMatrix.decompose()

                bone.scale.initValue = self.createVector3FromBlenderVector(m3SpaceScale)
                bone.scale.nullValue = self.createVector3(0.0, 0.0, 0.0)
                bone.rotation.initValue = self.createQuaternionFromBlenderQuaternion(m3SpaceRotation)
                bone.rotation.nullValue = self.createQuaternion(0.0, 0.0, 0.0, 1.0)
                bone.location.initValue = self.createVector3FromBlenderVector(m3SpaceLocation)
                bone.location.nullValue = self.createVector3(0.0, 0.0, 0.0)
                self.boneNameToM3SpaceDefaultLocationMap[boneName] = m3SpaceLocation
                self.boneNameToM3SpaceDefaultRotationMap[boneName] = m3SpaceRotation
                self.boneNameToM3SpaceDefaultScaleMap[boneName] = m3SpaceScale

                # calculate the bind matrix / absoluteInverseRestPoseMatrixFixed
                absRestPosMatrixFixed = absRestPosMatrix @ shared.rotFixMatrixInverted
                bindScale = blenderBone.m3_bind_scale
                bindScaleMatrix = shared.scaleVectorToMatrix(bindScale)
                absoluteInverseRestPoseMatrixFixed = absRestPosMatrixFixed.inverted()
                absoluteInverseRestPoseMatrixFixed = bindScaleMatrix @ absoluteInverseRestPoseMatrixFixed
                absoluteInverseBoneRestPos = self.createRestPositionFromBlender4x4Matrix(absoluteInverseRestPoseMatrixFixed)
                model.absoluteInverseBoneRestPositions.append(absoluteInverseBoneRestPos)

                self.boneIndexToAbsoluteInverseRestPoseMatrixFixedMap[boneIndex] = absoluteInverseRestPoseMatrixFixed

                boneNameToAbsInvRestPoseMatrix[blenderBone.name] = absRestPosMatrix.inverted()

                # Calculate the absolute matrix of this bone in default position
                # for later default boundings calculation
                absoluteBoneMatrix = m3PoseMatrix

                if (bone.parent != -1):
                    # The parent matrix has it's absoluteInverseRestPoseMatrixFixed multiplied to it. It needs to be undone:
                    parentMatrix = self.boneIndexToDefaultAbsoluteMatrixMap[bone.parent] @ self.boneIndexToAbsoluteInverseRestPoseMatrixFixedMap[bone.parent].inverted()
                    absoluteBoneMatrix = parentMatrix @ absoluteBoneMatrix

                absoluteBoneMatrix = absoluteBoneMatrix @ absoluteInverseRestPoseMatrixFixed

                self.boneIndexToDefaultAbsoluteMatrixMap[boneIndex] = absoluteBoneMatrix
        startTime = time.time()
        self.initBoneAnimations(model)
        endTime = time.time()
        duration = endTime - startTime
        print("Bone animation export took %s seconds" % duration)

    def initBoneAnimations(self, model):
        for animationIndex in self.animationIndicesToExport:
            animation = self.scene.m3_animations[animationIndex]
            print("Calculating bone movement done in animation %s" % animation.name)
            self.scene.m3_animation_index = animationIndex
            frames = set()
            # For animated rotations all frames are needed,
            # since Starcraft 2 isn't correcting the linearly interpolated values
            # In addition the bone matrices are needed for each frame
            # to calculate the mesh boundings in a later step
            #
            frames = self.allFramesOfAnimation(animation)
            timeValuesInMS = self.allFramesToMSValues(frames)

            frameToBoneIndexToAbsoluteMatrixMap = self.animationNameToFrameToBoneIndexToAbsoluteMatrixMap.get(animation.name)
            if frameToBoneIndexToAbsoluteMatrixMap is None:
                frameToBoneIndexToAbsoluteMatrixMap = {}
                self.animationNameToFrameToBoneIndexToAbsoluteMatrixMap[animation.name] = frameToBoneIndexToAbsoluteMatrixMap

            boneNameToLocations = {}
            boneNameToRotations = {}
            boneNameToScales = {}
            for armatureObjectName, boneNamesOfArmature in self.armatureObjectNameToBoneNamesMap.items():
                for boneName in boneNamesOfArmature:
                    boneNameToLocations[boneName] = []
                    boneNameToRotations[boneName] = []
                    boneNameToScales[boneName] = []

            # Jog animation frame so that complicated bone constraints are given time to be properly calculated before proceeding
            self.scene.frame_set(0)

            for frame in frames:
                self.scene.frame_set(frame)
                for armatureObjectName, boneNamesOfArmature in self.armatureObjectNameToBoneNamesMap.items():
                    armatureObject = bpy.data.objects[armatureObjectName]
                    for boneName in boneNamesOfArmature:
                        boneIndex = self.boneNameToBoneIndexMap[boneName]
                        bone = model.bones[boneIndex]
                        poseBone = armatureObject.pose.bones[boneName]

                        leftCorrectionMatrix = self.boneNameToLeftCorrectionMatrix[boneName]
                        rightCorrectionMatrix = self.boneNameToRightCorrectionMatrix[boneName]

                        poseMatrix = armatureObject.convert_space(
                            pose_bone=poseBone,
                            matrix=poseBone.matrix,
                            from_space='POSE',
                            to_space='LOCAL',
                        )

                        m3PoseMatrix = leftCorrectionMatrix @ poseMatrix @ rightCorrectionMatrix

                        boneIndexToAbsoluteMatrixMap = frameToBoneIndexToAbsoluteMatrixMap.get(frame)
                        if boneIndexToAbsoluteMatrixMap is None:
                            boneIndexToAbsoluteMatrixMap = {}
                            frameToBoneIndexToAbsoluteMatrixMap[frame] = boneIndexToAbsoluteMatrixMap

                        absoluteBoneMatrix = m3PoseMatrix
                        if (bone.parent != -1):
                            # The parent matrix has it's absoluteInverseRestPoseMatrixFixed multiplied to it. It needs to be undone:
                            parentMatrix = boneIndexToAbsoluteMatrixMap[bone.parent] @ self.boneIndexToAbsoluteInverseRestPoseMatrixFixedMap[bone.parent].inverted()
                            absoluteBoneMatrix = parentMatrix @ absoluteBoneMatrix

                        absoluteInverseRestPoseMatrixFixed = self.boneIndexToAbsoluteInverseRestPoseMatrixFixedMap[boneIndex]

                        absoluteBoneMatrix = absoluteBoneMatrix @ absoluteInverseRestPoseMatrixFixed

                        boneIndexToAbsoluteMatrixMap[boneIndex] = absoluteBoneMatrix

                        locations = boneNameToLocations[boneName]
                        rotations = boneNameToRotations[boneName]
                        scales = boneNameToScales[boneName]
                        loc, rot, sca = m3PoseMatrix.decompose()
                        locations.append(loc)
                        rotations.append(rot)
                        scales.append(sca)

            for armatureObjectName, boneNamesOfArmature in self.armatureObjectNameToBoneNamesMap.items():
                for boneName in boneNamesOfArmature:
                    boneIndex = self.boneNameToBoneIndexMap[boneName]
                    bone = model.bones[boneIndex]
                    locations = boneNameToLocations[boneName]
                    rotations = boneNameToRotations[boneName]
                    scales = boneNameToScales[boneName]

                    self.makeQuaternionsInterpolatable(rotations)
                    animIdToAnimDataMap = self.nameToAnimIdToAnimDataMap[animation.name]

                    m3SpaceLocation = self.boneNameToM3SpaceDefaultLocationMap[boneName]
                    m3SpaceRotation = self.boneNameToM3SpaceDefaultRotationMap[boneName]
                    m3SpaceScale = self.boneNameToM3SpaceDefaultScaleMap[boneName]

                    locationAnimPath = 'pose.bones["%s"].location' % boneName
                    rotationAnimPath = 'pose.bones["%s"].rotation_quaternion' % boneName
                    scaleAnimPath = 'pose.bones["%s"].scale' % boneName

                    locationAnimId = self.getAnimIdFor(shared.animObjectIdArmature, locationAnimPath)
                    rotationAnimId = self.getAnimIdFor(shared.animObjectIdArmature, rotationAnimPath)
                    scaleAnimId = self.getAnimIdFor(shared.animObjectIdArmature, scaleAnimPath)

                    if self.isAnimationExport or self.vectorArrayContainsNotOnly(locations, m3SpaceLocation):
                        locationTimeValuesInMS, locations = shared.simplifyVectorAnimationWithInterpolation(timeValuesInMS, locations)
                        m3Locs = self.createVector3sFromBlenderVectors(locations)
                        m3AnimBlock = self.createInstanceOf("SD3V")
                        m3AnimBlock.frames = locationTimeValuesInMS
                        m3AnimBlock.flags = 0
                        m3AnimBlock.fend = self.frameToMS(animation.exlusiveEndFrame)
                        m3AnimBlock.keys = m3Locs
                        animIdToAnimDataMap[locationAnimId] = m3AnimBlock
                        bone.location.header.animFlags = shared.animFlagsForAnimatedProperty
                        bone.setNamedBit("flags", "animated", True)

                    if self.isAnimationExport or self.quaternionArrayContainsNotOnly(rotations, m3SpaceRotation):
                        rotationTimeValuesInMS, rotations = shared.simplifyQuaternionAnimationWithInterpolation(timeValuesInMS, rotations)
                        m3Rots = self.createQuaternionsFromBlenderQuaternions(rotations)
                        m3AnimBlock = self.createInstanceOf("SD4Q")
                        m3AnimBlock.frames = rotationTimeValuesInMS
                        m3AnimBlock.flags = 0
                        m3AnimBlock.fend = self.frameToMS(animation.exlusiveEndFrame)
                        m3AnimBlock.keys = m3Rots
                        animIdToAnimDataMap[rotationAnimId] = m3AnimBlock
                        bone.rotation.header.animFlags = shared.animFlagsForAnimatedProperty
                        bone.setNamedBit("flags", "animated", True)

                    if self.isAnimationExport or self.vectorArrayContainsNotOnly(scales, m3SpaceScale):
                        scaleTimeValuesInMS, scales = shared.simplifyVectorAnimationWithInterpolation(timeValuesInMS, scales)
                        m3Scas = self.createVector3sFromBlenderVectors(scales)
                        m3AnimBlock = self.createInstanceOf("SD3V")
                        m3AnimBlock.frames = scaleTimeValuesInMS
                        m3AnimBlock.flags = 0
                        m3AnimBlock.fend = self.frameToMS(animation.exlusiveEndFrame)
                        m3AnimBlock.keys = m3Scas
                        animIdToAnimDataMap[scaleAnimId] = m3AnimBlock
                        bone.scale.header.animFlags = shared.animFlagsForAnimatedProperty
                        bone.setNamedBit("flags", "animated", True)

    def initVisibilityTest(self, model):
        halfSize = self.scene.m3_visibility_test.size / 2.0
        minBorder = self.scene.m3_visibility_test.center - halfSize
        maxBorder = self.scene.m3_visibility_test.center + halfSize
        model.boundings.radius = self.scene.m3_visibility_test.radius
        model.boundings.minBorder = self.blenderToM3Vector(minBorder)
        model.boundings.maxBorder = self.blenderToM3Vector(maxBorder)

    def allFramesOfAnimation(self, animation):
        # In Starcraft 2 there is one more key frame then there is usually in Blender:
        # 3 Blender key frames at the times 0, 33, 67 give a an animation for the time 0 to 100 (at 30 FPS)
        # For Starcraft 2 4 key frames are needed: 0, 33, 67 and 100.
        # For a smooth loop the key frame data of 0 and 100 need to be the same.
        return list(range(animation.startFrame, animation.exlusiveEndFrame + 1))

    def vectorArrayContainsNotOnly(self, vectorArray, vector):
        for v in vectorArray:
            if not shared.vectorsAlmostEqual(vector, v):
                return True
        return False

    def quaternionArrayContainsNotOnly(self, quaternionArray, quaternion):
        for q in quaternionArray:
            if not shared.quaternionsAlmostEqual(quaternion, q):
                return True
        return False

    def initOldReferenceIndicesInCorrectedOrder(self):
        scene = self.scene
        materialNameToOldReferenceIndexMap = {}
        for materialReferenceIndex, materialReference in enumerate(self.scene.m3_material_references):
            materialNameToOldReferenceIndexMap[materialReference.name] = materialReferenceIndex

        remainingMaterials = list(range(len(self.scene.m3_material_references)))
        self.oldReferenceIndicesInCorrectedOrder = []
        while len(remainingMaterials) > 0:
            unableToDefineChildsFirst = True
            for oldReferenceIndex in remainingMaterials:
                reference = scene.m3_material_references[oldReferenceIndex]
                canBeDefined = True
                if reference.materialType == shared.compositeMaterialTypeIndex:
                    compositeMaterial = scene.m3_composite_materials[reference.materialIndex]
                    for sectionIndex, section in enumerate(compositeMaterial.sections):
                        oldChildReferenceIndex = materialNameToOldReferenceIndexMap.get(section.name)
                        if oldChildReferenceIndex is None:
                            raise ExportError("The composite material %s uses '%s' as material, but no m3 material with that name exist!" % (compositeMaterial.name, section.name))
                        if oldChildReferenceIndex not in self.oldReferenceIndicesInCorrectedOrder:
                            canBeDefined = False

                if canBeDefined:
                    remainingMaterials.remove(oldReferenceIndex)
                    self.oldReferenceIndicesInCorrectedOrder.append(oldReferenceIndex)
                    unableToDefineChildsFirst = False
                    break
            if unableToDefineChildsFirst:
                raise Exception("Unable to define all sections before the actual composite material: Is there a loop back?")

    def initMaterialNameToNewReferenceIndexMap(self):
        self.materialNameToNewReferenceIndexMap = {}
        for newRefeferenceIndex, oldReferenceIndex in enumerate(self.oldReferenceIndicesInCorrectedOrder):
            materialReference = self.scene.m3_material_references[oldReferenceIndex]
            self.materialNameToNewReferenceIndexMap[materialReference.name] = newRefeferenceIndex

    def initMesh(self, model):
        nonEmptyMeshObjects: List[bpy.types.Object] = []
        uvCoordinatesPerVertex = 1  # Never saw a m3 model with at least 1 UV layer
        for meshObject in shared.findMeshObjects(self.scene):
            mesh: bpy.types.Mesh = meshObject.data
            mesh.calc_loop_triangles()
            if len(mesh.loop_triangles) > 0 and not mesh.m3_physics_mesh:
                nonEmptyMeshObjects.append(meshObject)
            uvCoordinatesPerVertex = max(uvCoordinatesPerVertex, len(mesh.uv_layers))

        model.setNamedBit("flags", "hasMesh", len(nonEmptyMeshObjects) > 0)
        model.boundings = self.createAlmostEmptyBoundingsWithRadius(2.0)

        if len(nonEmptyMeshObjects) == 0:
            model.numberOfBonesToCheckForSkin = 0
            model.divisions = [self.createEmptyDivision()]
            return

        if uvCoordinatesPerVertex not in [1, 2, 3, 4]:
            raise Exception("The m3 format seems to supports only 1-4 UV layers per mesh, not %d" % uvCoordinatesPerVertex)

        model.vFlags = 0x182007d

        if uvCoordinatesPerVertex >= 2:
            model.setNamedBit("vFlags", "useUVChannel1", True)

        if uvCoordinatesPerVertex >= 3:
            model.setNamedBit("vFlags", "useUVChannel2", True)

        if uvCoordinatesPerVertex >= 4:
            model.setNamedBit("vFlags", "useUVChannel3", True)

        rgbColorChannelName = "color"
        alphaColorChannelName = "alpha"

        exportVertexRGBA = False
        for meshObjectToCheck in nonEmptyMeshObjects:
            meshToCheck: bpy.types.Mesh = meshObjectToCheck.data

            for vertexColorLayer in meshToCheck.vertex_colors:
                vertexColorLayerName = vertexColorLayer.name
                if vertexColorLayerName == rgbColorChannelName:
                    exportVertexRGBA = True
                elif vertexColorLayerName == alphaColorChannelName:
                    exportVertexRGBA = True
                else:
                    print("The mesh %s has has a color layer called %s. Only color layers with the names 'color' and 'alpha' can be exported" % (meshObjectToCheck.name, vertexColorLayerName))

        model.setNamedBit("vFlags", "hasVertexColors", exportVertexRGBA)

        m3VertexStructureDefinition = m3.structures["VertexFormat" + hex(model.vFlags)].getVersion(0)

        division = self.createInstanceOf("DIV_")
        model.divisions.append(division)
        m3Vertices = []
        for meshIndex, meshObject in enumerate(nonEmptyMeshObjects):
            mesh: bpy.types.Mesh = meshObject.data
            print("Exporting mesh object %s" % meshObject.name)

            signGroup = mesh.polygon_layers_int.get("m3sign") or mesh.polygon_layers_int.new(name="m3sign")

            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            self.scene.view_layers[0].objects.active = meshObject
            meshObject.select_set(True)
            bpy.ops.object.duplicate()
            meshObjectCopy = self.scene.view_layers[0].objects.active
            bpy.ops.object.modifier_apply(modifier='EdgeSplit')
            mesh = meshObjectCopy.data
            meshObject = meshObjectCopy
            mesh.update()

            materialReferenceIndex = self.materialNameToNewReferenceIndexMap.get(mesh.m3_material_name)
            if materialReferenceIndex is None:
                raise ExportError("The mesh %s uses '%s' as material, but no m3 material with that name exist!" % (mesh.name, mesh.m3_material_name))

            firstBoneLookupIndex = len(model.boneLookup)
            staticMeshBoneName = "StaticMesh"
            boneNameToBoneLookupIndexMap = {}
            boneNamesOfArmature = set()
            if len(meshObject.modifiers) == 0:
                pass
            elif len(meshObject.modifiers) == 1 and (meshObject.modifiers[0].type == "ARMATURE"):
                modifier = meshObject.modifiers[0]
                armatureObject = modifier.object
                if armatureObject is not None:
                    armature = armatureObject.data
                    for blenderBoneIndex, blenderBone in enumerate(armature.bones):
                        boneNamesOfArmature.add(blenderBone.name)
            else:
                raise ExportError("The mesh %s has invalid modifiers: Mesh must have no modifiers except single one for the armature and one for edge split." % meshObject.name)
            objectToWorldMatrix = meshObject.matrix_world

            vertexColor = mesh.vertex_colors.get(rgbColorChannelName)
            if vertexColor is not None:
                vertexColorData = vertexColor.data
            else:
                vertexColorData = None
            vertexAlpha = mesh.vertex_colors.get(alphaColorChannelName)
            if vertexAlpha is not None:
                vertexAlphaData = vertexAlpha.data
            else:
                vertexAlphaData = None

            firstFaceVertexIndexIndex = len(division.faces)
            firstVertexIndexIndex = len(m3Vertices)
            regionFaceVertexIndices = []
            regionVertices = []
            vertexDataTupleToIndexMap = {}
            nextVertexIndex = 0
            numberOfBoneWeightPairsPerVertex = 0
            staticMeshBoneLookupIndex = None
            mesh.calc_loop_triangles()

            def normalize(x, y, z):
                length = math.sqrt(x * x + y * y + z * z)
                if length == 0:
                    return 0.0, 0.0, 0.0
                return (x / length, y / length, z / length)

            for tri in mesh.loop_triangles:
                assert(len(tri.vertices) == 3)

                # Calculate tangents

                vertex0 = meshObject.data.vertices[tri.vertices[0]]
                vertex1 = meshObject.data.vertices[tri.vertices[1]]
                vertex2 = meshObject.data.vertices[tri.vertices[2]]

                uv0 = meshObject.data.uv_layers[0].data[tri.loops[0]].uv
                uv1 = meshObject.data.uv_layers[0].data[tri.loops[1]].uv
                uv2 = meshObject.data.uv_layers[0].data[tri.loops[2]].uv

                v0 = uv0[1]
                v1 = uv1[1]
                v2 = uv2[1]

                deltaV1 = v1 - v0
                deltaV2 = v2 - v0

                e1x = vertex1.co.x - vertex0.co.x
                e1y = vertex1.co.y - vertex0.co.y
                e1z = vertex1.co.z - vertex0.co.z

                e2x = vertex2.co.x - vertex0.co.x
                e2y = vertex2.co.y - vertex0.co.y
                e2z = vertex2.co.z - vertex0.co.z

                tx = (deltaV2 * e1x - deltaV1 * e2x)
                ty = (deltaV2 * e1y - deltaV1 * e2y)
                tz = (deltaV2 * e1z - deltaV1 * e2z)
                tx, ty, tz = normalize(tx, ty, tz)

                for faceRelativeVertexIndex, vertIndex in enumerate(tri.vertices):
                    blenderVertex = mesh.vertices[vertIndex]
                    m3Vertex = m3VertexStructureDefinition.createInstance()

                    absolutePosition = objectToWorldMatrix @ blenderVertex.co
                    m3Vertex.position = self.blenderToM3Vector(absolutePosition)

                    weightLookupIndexPairs = []
                    for gIndex, g in enumerate(blenderVertex.groups):
                        vertexGroupIndex = g.group
                        # It seems like the group data can become corrupted in Blender:
                        if vertexGroupIndex < len(meshObject.vertex_groups):
                            vertexGroup = meshObject.vertex_groups[vertexGroupIndex]
                            boneIndex = self.boneNameToBoneIndexMap.get(vertexGroup.name)
                            if boneIndex is not None and vertexGroup.name in boneNamesOfArmature:
                                boneLookupIndex = boneNameToBoneLookupIndexMap.get(vertexGroup.name)
                                if boneLookupIndex is None:
                                    boneLookupIndex = len(model.boneLookup) - firstBoneLookupIndex
                                    model.boneLookup.append(boneIndex)
                                    boneNameToBoneLookupIndexMap[vertexGroup.name] = boneLookupIndex
                                bone = model.bones[boneIndex]
                                bone.setNamedBit("flags", "skinned", True)
                                boneWeight = sorted((round(g.weight * 255), 0, 255))[1]
                                if boneWeight != 0:
                                    if len(weightLookupIndexPairs) < 4:
                                        weightLookupIndexPairs.append((g.weight, boneLookupIndex))

                    totalWeight = 0
                    for weight, lookupIndex in weightLookupIndexPairs:
                        totalWeight += weight

                    # This algorithm is aiming at ensuring that roundedWeightSum is 255 at the end
                    # Since correctedWeightSum is  1.0000XXXXX at the end,
                    # roundedWeightSum will be exactly 255.
                    roundedWeightLookupIndexPairs = []
                    correctedWeightSum = 0.0
                    roundedWeightSum = 0
                    for weight, lookupIndex in weightLookupIndexPairs:
                        correctedWeight = weight / totalWeight
                        correctedWeightSum += correctedWeight
                        newRoundedWeithSum = round(correctedWeightSum * 255.0)
                        roundedWeight = newRoundedWeithSum - roundedWeightSum
                        roundedWeightSum = newRoundedWeithSum
                        roundedWeightLookupIndexPairs.append((roundedWeight, lookupIndex))

                    weightIndex = 0
                    for roundedWeight, lookupIndex in roundedWeightLookupIndexPairs:
                        setattr(m3Vertex, "boneWeight%d" % weightIndex, roundedWeight)
                        setattr(m3Vertex, "boneLookupIndex%d" % weightIndex, lookupIndex)
                        weightIndex += 1

                    isStaticVertex = (len(roundedWeightLookupIndexPairs) == 0)
                    if isStaticVertex:
                        staticMeshBoneIndex = self.boneNameToBoneIndexMap.get(staticMeshBoneName)
                        if staticMeshBoneIndex is None:
                            staticMeshBoneIndex = self.addBoneWithRestPosAndReturnIndex(model, staticMeshBoneName, realBone=True)
                            self.createBoneMatricesForStaticMeshBone(staticMeshBoneIndex)
                        if staticMeshBoneLookupIndex is None:
                            staticMeshBoneLookupIndex = boneNameToBoneLookupIndexMap.get(staticMeshBoneName)
                            if staticMeshBoneLookupIndex is None:
                                self.boneNameToBoneIndexMap[staticMeshBoneName] = staticMeshBoneIndex
                                staticMeshBoneLookupIndex = len(model.boneLookup) - firstBoneLookupIndex
                                model.boneLookup.append(staticMeshBoneIndex)
                                boneNameToBoneLookupIndexMap[staticMeshBoneName] = staticMeshBoneLookupIndex
                        bone = model.bones[staticMeshBoneIndex]
                        bone.setNamedBit("flags", "skinned", True)
                        roundedWeightLookupIndexPairs.append((255, staticMeshBoneLookupIndex))

                    usedBoneWeightSlots = len(roundedWeightLookupIndexPairs)
                    if usedBoneWeightSlots > numberOfBoneWeightPairsPerVertex:
                        numberOfBoneWeightPairsPerVertex = usedBoneWeightSlots

                    for uvLayerIndex in range(0, uvCoordinatesPerVertex):
                        m3AttributeName = "uv" + str(uvLayerIndex)
                        if len(mesh.uv_layers) > uvLayerIndex:
                            uvData = mesh.uv_layers[uvLayerIndex].data[tri.loops[faceRelativeVertexIndex]]
                            m3UVCoord = self.convertBlenderToM3UVCoordinates(uvData.uv)
                            setattr(m3Vertex, m3AttributeName, m3UVCoord)
                        else:
                            setattr(m3Vertex, m3AttributeName, self.createM3UVVector(0.0, 0.0))

                    m3Vertex.normal = self.blenderVector3ToVector3As3Fixed8(blenderVertex.normal)

                    if signGroup.data[tri.polygon_index].value == 1:
                        m3Vertex.sign = 1.0
                        m3Vertex.tangent.x = -tx
                        m3Vertex.tangent.y = -ty
                        m3Vertex.tangent.z = -tz
                    else:
                        m3Vertex.sign = -1.0
                        m3Vertex.tangent.x = tx
                        m3Vertex.tangent.y = ty
                        m3Vertex.tangent.z = tz

                    # TODO: unsure if this actually works as intended.. find a model for test
                    red = 1.0
                    green = 1.0
                    blue = 1.0
                    alpha = 1.0
                    if exportVertexRGBA:
                        if vertexColorData is not None:
                            blenderColor = vertexColorData[tri.loops[faceRelativeVertexIndex]].color
                            red = blenderColor[0]
                            green = blenderColor[1]
                            blue = blenderColor[2]
                        if vertexAlphaData is not None:
                            blenderColor = vertexAlphaData[tri.loops[faceRelativeVertexIndex]].color
                            alpha = (blenderColor[0] + blenderColor[1] + blenderColor[2]) / 3.0
                        m3Vertex.color = self.createColor(red, green, blue, alpha)

                    v = m3Vertex
                    vertexIdList = []
                    vertexIdList.extend((v.position.x, v.position.y, v.position.z))
                    vertexIdList.extend((v.boneWeight0, v.boneWeight1, v.boneWeight2, v.boneWeight3))
                    vertexIdList.extend((v.boneLookupIndex0, v.boneLookupIndex1, v.boneLookupIndex2, v.boneLookupIndex3))
                    vertexIdList.extend((v.normal.x, v.normal.y, v.normal.z))
                    if exportVertexRGBA:
                        vertexIdList.extend((red, green, blue, alpha))
                    for i in range(uvCoordinatesPerVertex):
                        uvAttribute = "uv" + str(i)
                        uvVector = getattr(v, uvAttribute)
                        vertexIdList.append(uvVector.x)
                        vertexIdList.append(uvVector.y)
                    vertexIdTuple = tuple(vertexIdList)

                    vertexIndex = vertexDataTupleToIndexMap.get(vertexIdTuple)
                    if vertexIndex is None:
                        vertexIndex = nextVertexIndex
                        vertexDataTupleToIndexMap[vertexIdTuple] = vertexIndex
                        nextVertexIndex += 1
                        regionVertices.append(m3Vertex)
                        m3VertexStructureDefinition.validateInstance(m3Vertex, "vertex")
                    regionFaceVertexIndices.append(vertexIndex)

            division.faces.extend(regionFaceVertexIndices)
            m3Vertices.extend(regionVertices)

            region = self.createInstanceOf("REGN")
            region.firstVertexIndex = firstVertexIndexIndex
            region.numberOfVertices = len(regionVertices)
            region.firstFaceVertexIndexIndex = firstFaceVertexIndexIndex
            region.numberOfFaceVertexIndices = len(regionFaceVertexIndices)
            region.numberOfBones = len(boneNameToBoneLookupIndexMap)
            region.firstBoneLookupIndex = firstBoneLookupIndex
            region.numberOfBoneLookupIndices = len(boneNameToBoneLookupIndexMap)
            region.rootBoneIndex = model.boneLookup[firstBoneLookupIndex]
            region.numberOfBoneWeightPairsPerVertex = numberOfBoneWeightPairsPerVertex
            division.regions.append(region)

            m3Object = self.createInstanceOf("BAT_")
            m3Object.regionIndex = meshIndex
            materialReferenceIndex = self.materialNameToNewReferenceIndexMap.get(mesh.m3_material_name)
            if materialReferenceIndex is None:
                raise ExportError("The mesh %s uses '%s' as material, but no m3 material with that name exist!" % (mesh.name, mesh.m3_material_name))
            m3Object.materialReferenceIndex = materialReferenceIndex

            division.objects.append(m3Object)

            bpy.ops.object.delete()

        numberOfBonesToCheckForSkin = 0
        for boneIndex, bone in enumerate(model.bones):
            if bone.getNamedBit("flags", "skinned"):
                numberOfBonesToCheckForSkin = boneIndex + 1
        model.numberOfBonesToCheckForSkin = numberOfBonesToCheckForSkin

        model.vertices = m3VertexStructureDefinition.instancesToBytes(m3Vertices)

        startTime = time.time()
        self.initMeshBoundings(model, m3Vertices)
        endTime = time.time()
        duration = endTime - startTime
        print("Mesh boundings animation export took %s seconds" % duration)

    def initMeshBoundings(self, model, m3Vertices):
        boundingsAnimRef = self.createInstanceOf("BNDSV0AnimationReference")
        animHeader = self.createInstanceOf("AnimationReferenceHeader")
        animHeader.interpolationType = 0
        animHeader.animFlags = 0x0
        animHeader.animId = self.boundingAnimId  # boudings seem to have always this id
        boundingsAnimRef.header = animHeader
        self.initBoundingPointsOfExportedBonesList(model, m3Vertices)
        defaultBoundingsVector = self.calculateBoundingsVector(model, m3Vertices, self.boneIndexToDefaultAbsoluteMatrixMap)
        boundingsAnimRef.initValue = self.createBNDSFromVector(defaultBoundingsVector)
        boundingsAnimRef.nullValue = self.createBoundings(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        for animationIndex in self.animationIndicesToExport:
            animation = self.scene.m3_animations[animationIndex]
            print("Calculating mesh boundings for animation %s" % animation.name)
            frameToBoneIndexToAbsoluteMatrixMap = self.animationNameToFrameToBoneIndexToAbsoluteMatrixMap[animation.name]
            boundingsVectorList = []
            frames = self.allFramesOfAnimation(animation)
            timeValuesInMS = self.allFramesToMSValues(frames)
            for frame in frames:
                boneIndexToAbsoluteMatrixMap = frameToBoneIndexToAbsoluteMatrixMap[frame]
                b = self.calculateBoundingsVector(model, m3Vertices, boneIndexToAbsoluteMatrixMap)
                boundingsVectorList.append(b)

            if self.isAnimationExport or self.vectorArrayContainsNotOnly(boundingsVectorList, defaultBoundingsVector):
                timeValuesInMS, boundingsVectorList = shared.simplifyVectorAnimationWithInterpolation(timeValuesInMS, boundingsVectorList)
                boundingStructures = list(self.createBNDSFromVector(v) for v in boundingsVectorList)
                m3AnimBlock = self.createInstanceOf("SDMB")
                m3AnimBlock.frames = timeValuesInMS
                m3AnimBlock.flags = 0
                m3AnimBlock.fend = self.frameToMS(animation.exlusiveEndFrame)
                m3AnimBlock.keys = boundingStructures

                animIdToAnimDataMap = self.nameToAnimIdToAnimDataMap[animation.name]
                animIdToAnimDataMap[self.boundingAnimId] = m3AnimBlock
                boundingsAnimRef.header.animFlags = shared.animFlagsForAnimatedProperty

        msec = self.createInstanceOf("MSEC")
        msec.boundingsAnimation = boundingsAnimRef
        model.divisions[0].msec.append(msec)

    def createBoneMatricesForStaticMeshBone(self, staticMeshBoneIndex):
        self.boneIndexToDefaultAbsoluteMatrixMap[staticMeshBoneIndex] = mathutils.Matrix()
        for animationIndex in self.animationIndicesToExport:
            animation = self.scene.m3_animations[animationIndex]
            frameToBoneIndexToAbsoluteMatrixMap = self.animationNameToFrameToBoneIndexToAbsoluteMatrixMap.get(animation.name)
            if frameToBoneIndexToAbsoluteMatrixMap is None:
                frameToBoneIndexToAbsoluteMatrixMap = {}
                self.animationNameToFrameToBoneIndexToAbsoluteMatrixMap[animation.name] = frameToBoneIndexToAbsoluteMatrixMap
            for frame in self.allFramesOfAnimation(animation):
                boneIndexToAbsoluteMatrixMap = frameToBoneIndexToAbsoluteMatrixMap.get(frame)
                if boneIndexToAbsoluteMatrixMap is None:
                    boneIndexToAbsoluteMatrixMap = {}
                    frameToBoneIndexToAbsoluteMatrixMap[frame] = boneIndexToAbsoluteMatrixMap
                boneIndexToAbsoluteMatrixMap[staticMeshBoneIndex] = mathutils.Matrix()

    def createBNDSFromVector(self, vector):
        minX = vector[0]
        minY = vector[1]
        minZ = vector[2]
        maxX = vector[3]
        maxY = vector[4]
        maxZ = vector[5]
        radius = vector[6]
        b = self.createInstanceOf("BNDS")
        b.minBorder = self.createVector3(minX, minY, minZ)
        b.maxBorder = self.createVector3(maxX, maxY, maxZ)
        b.radius = radius
        return b

    def calculateBoundingsVector(self, model, m3Vertices, boneIndexToAbsoluteMatrixMap):
        minX2 = float("inf")
        minY2 = float("inf")
        minZ2 = float("inf")
        maxX2 = -float("inf")
        maxY2 = -float("inf")
        maxZ2 = -float("inf")
        for boneIndex, boudingPoints in enumerate(self.boundingPointsOfExportedBones):
            if len(boudingPoints) > 0:
                boneMatrix = boneIndexToAbsoluteMatrixMap[boneIndex]
                minXBone = float("inf")
                minYBone = float("inf")
                minZBone = float("inf")
                maxXBone = -float("inf")
                maxYBone = -float("inf")
                maxZBone = -float("inf")
                for untransformedPosition in boudingPoints:
                    positionTransformedByBone = boneMatrix @ untransformedPosition
                    minXBone = min(minXBone, positionTransformedByBone.x)
                    minYBone = min(minYBone, positionTransformedByBone.y)
                    minZBone = min(minZBone, positionTransformedByBone.z)
                    maxXBone = max(maxXBone, positionTransformedByBone.x)
                    maxYBone = max(maxYBone, positionTransformedByBone.y)
                    maxZBone = max(maxZBone, positionTransformedByBone.z)

                minX2 = min(minX2, minXBone)
                minY2 = min(minY2, minYBone)
                minZ2 = min(minZ2, minZBone)
                maxX2 = max(maxX2, maxXBone)
                maxY2 = max(maxY2, maxYBone)
                maxZ2 = max(maxZ2, maxZBone)
                # print("Bone %s,  (%2f %2f %2f) to (%2f %2f %2f)" %(model.bones[boneIndex].name, minXBone, minYBone, minZBone, maxXBone, maxYBone,maxZBone))

        visualizeBoundingBoxes = False

        # Debug code to visualize boundings:
        if visualizeBoundingBoxes:
            def selectOrCreateBone(scene, boneName, location):
                "Returns the bone and it's pose variant"
                if bpy.ops.object.mode_set.poll():
                    bpy.ops.object.mode_set(mode='OBJECT')
                if bpy.ops.object.select_all.poll():
                    bpy.ops.object.select_all(action='DESELECT')
                bone, armatureObject = shared.findBoneWithArmatureObject(scene, boneName)
                boneExists = bone is not None
                if boneExists:
                    armature = armatureObject.data
                    armatureObject.select_set(True)
                    scene.view_layers[0].objects.active = armatureObject
                else:
                    armatureObject = shared.findArmatureObjectForNewBone(scene)
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
                    editBone.head = location
                    editBone.tail = (editBone.head[0] + 0.05, editBone.head[1], editBone.head[2])

                if bpy.ops.object.mode_set.poll():
                    bpy.ops.object.mode_set(mode='POSE')
                scene.view_layers[0].objects.active = armatureObject
                armatureObject.select_set(True)
                for currentBone in armature.bones:
                    currentBone.select = currentBone.name == boneName
                poseBone = armatureObject.pose.bones[boneName]
                bone = armatureObject.data.bones[boneName]
                return (bone, poseBone)
            for boneIndex, boudingPoints in enumerate(self.boundingPointsOfExportedBones):
                boneMatrix = boneIndexToAbsoluteMatrixMap[boneIndex]
                minXBone = float("inf")
                minYBone = float("inf")
                minZBone = float("inf")
                maxXBone = -float("inf")
                maxYBone = -float("inf")
                maxZBone = -float("inf")
                transformedPositions = []
                for untransformedPosition in boudingPoints:
                    positionTransformedByBone = boneMatrix @ untransformedPosition
                    transformedPositions.append(positionTransformedByBone)
                if len(boudingPoints) >= 8:
                    mesh = bpy.data.meshes.new("debug_" + model.bones[boneIndex].name)
                    mesh.from_pydata(vertices=transformedPositions, faces=[], edges=[(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)])
                    mesh.update(calc_edges=True)
                    mesh.m3_physics_mesh = True

                    meshObject = bpy.data.objects.new(mesh.name, mesh)
                    meshObject.location = (0, 0, 0)
                    meshObject.show_name = True

                    self.scene.collection.objects.link(meshObject)

            particle_system = self.scene.m3_particle_systems.add()
            particle_system.updateBlenderBoneShapes = False
            particle_system.name = "debug_boundings"
            particle_system.boneName = particle_system.name
            boundingsCenter = mathutils.Vector(((minX2 + maxX2) / 2.0, (minY2 + maxY2) / 2.0, (minZ2 + maxZ2) / 2.0))
            bone, poseBone = selectOrCreateBone(self.scene, particle_system.boneName, boundingsCenter)
            particle_system.emissionAreaSize = (maxX2 - minX2, maxY2 - minY2, maxZ2 - minZ2)
            particle_system.emissionAreaType = shared.emissionAreaTypeCuboid
            shared.updateBoneShapeOfParticleSystem(particle_system, bone, poseBone)
            particle_system.updateBlenderBoneShapes = True
            raise Exception("Aborting to visualize bounding boxes")

        diffV = mathutils.Vector(((maxX2 - minX2), (maxY2 - minY2), (maxZ2 - minZ2)))
        radius = diffV.length / 2
        return mathutils.Vector((minX2, minY2, minZ2, maxX2, maxY2, maxZ2, radius))

    def initBoundingPointsOfExportedBonesList(self, model, m3Vertices):
        pointsOfExportedBones = []
        for index in range(len(self.restPositionsOfExportedBones)):
            pointsOfExportedBones.append([])

        for division in model.divisions:
            for region in division.regions:
                regionVertexIndices = range(region.firstVertexIndex, region.firstVertexIndex + region.numberOfVertices)
                boneIndexLookup = model.boneLookup[region.firstBoneLookupIndex:region.firstBoneLookupIndex + region.numberOfBoneLookupIndices]
                for vertexIndex in regionVertexIndices:
                    m3Vertex = m3Vertices[vertexIndex]
                    boneWeightsAsInt = [m3Vertex.boneWeight0, m3Vertex.boneWeight1, m3Vertex.boneWeight2, m3Vertex.boneWeight3]
                    boneLookupIndices = [m3Vertex.boneLookupIndex0, m3Vertex.boneLookupIndex1, m3Vertex.boneLookupIndex2, m3Vertex.boneLookupIndex3]
                    vertexPosition = mathutils.Vector((m3Vertex.position.x, m3Vertex.position.y, m3Vertex.position.z))
                    for boneWeightAsInt, boneLookupIndex in zip(boneWeightsAsInt, boneLookupIndices):
                        if boneWeightAsInt != 0:
                            boneIndex = boneIndexLookup[boneLookupIndex]
                            pointsOfExportedBones[boneIndex].append(vertexPosition)

        self.boundingPointsOfExportedBones = []
        for vertexPositions in pointsOfExportedBones:
            boundingPoints = []
            if len(vertexPositions) > 0:
                minX = float("inf")
                minY = float("inf")
                minZ = float("inf")
                maxX = -float("inf")
                maxY = -float("inf")
                maxZ = -float("inf")

                for vertexPosition in vertexPositions:
                    minX = min(minX, vertexPosition.x)
                    minY = min(minY, vertexPosition.y)
                    minZ = min(minZ, vertexPosition.z)
                    maxX = max(maxX, vertexPosition.x)
                    maxY = max(maxY, vertexPosition.y)
                    maxZ = max(maxZ, vertexPosition.z)
                boundingPoints.append(mathutils.Vector((minX, minY, minZ)))
                boundingPoints.append(mathutils.Vector((minX, maxY, minZ)))
                boundingPoints.append(mathutils.Vector((minX, maxY, maxZ)))
                boundingPoints.append(mathutils.Vector((minX, minY, maxZ)))
                boundingPoints.append(mathutils.Vector((maxX, minY, minZ)))
                boundingPoints.append(mathutils.Vector((maxX, maxY, minZ)))
                boundingPoints.append(mathutils.Vector((maxX, maxY, maxZ)))
                boundingPoints.append(mathutils.Vector((maxX, minY, maxZ)))
            self.boundingPointsOfExportedBones.append(boundingPoints)

    def findRootBoneIndex(self, model, boneIndices):
        boneIndexSet = set(boneIndices)
        for boneIndex in boneIndices:
            bone = model.bones[boneIndex]
            parentIndex = bone.parent
            isRoot = True
            while parentIndex != -1:
                if parentIndex in boneIndexSet:
                    isRoot = False
                parentBone = model.bones[parentIndex]
                parentIndex = parentBone.parent
            if isRoot:
                return boneIndex

    def makeQuaternionsInterpolatable(self, quaternions):
        if len(quaternions) < 2:
            return

        previousQuaternion = quaternions[0]
        for quaternion in quaternions[1:]:
            shared.smoothQuaternionTransition(previousQuaternion=previousQuaternion, quaternionToFix=quaternion)
            previousQuaternion = quaternion

    def blenderVector3ToVector3As3Fixed8(self, blenderVector3):
        x = blenderVector3.x
        y = blenderVector3.y
        z = blenderVector3.z
        return self.createVector3As3Fixed8(x, y, z)

    def createVector3As3Fixed8(self, x, y, z):
        m3Vector = self.createInstanceOf("Vector3As3Fixed8")
        m3Vector.x = x
        m3Vector.y = y
        m3Vector.z = z
        return m3Vector

    def createM3UVVector(self, x, y):
        m3UV = self.createInstanceOf("Vector2As2int16")
        m3UV.x = self.clampToInt16(round(x * 2048))
        m3UV.y = self.clampToInt16(round((1 - y) * 2048))
        return m3UV

    def clampToInt16(self, value):
        minInt16 = (-(1 << 15))
        maxInt16 = ((1 << 15) - 1)
        if value < minInt16:
            return minInt16
        if value > maxInt16:
            return maxInt16
        return value

    def convertBlenderToM3UVCoordinates(self, blenderUV):
        return self.createM3UVVector(blenderUV.x, blenderUV.y)

    def blenderToM3Vector(self, blenderVector3):
        return self.createVector3(blenderVector3.x, blenderVector3.y, blenderVector3.z)

    def addBoneWithRestPosAndReturnIndex(self, model, boneName, realBone):
        boneIndex = len(model.bones)
        bone = self.createStaticBoneAtOrigin(boneName, realBone=realBone)
        model.bones.append(bone)

        boneRestPos = self.createIdentityRestPosition()
        model.absoluteInverseBoneRestPositions.append(boneRestPos)
        self.restPositionsOfExportedBones.append(mathutils.Matrix())
        return boneIndex

    def findArmatureObjects(self) -> Iterable[bpy.types.Object]:
        for currentObject in self.scene.objects:
            if currentObject.type == 'ARMATURE':
                yield currentObject

    def frameToMS(self, frame):
        frameRate = 30  # Export always with frame rate 30 so that there is no compability issue
        return round((frame / frameRate) * 1000.0)

    def prepareAnimationEndEvents(self):
        for animationIndex in self.animationIndicesToExport:
            animation = self.scene.m3_animations[animationIndex]
            animIdToAnimDataMap = self.nameToAnimIdToAnimDataMap[animation.name]
            animEndId = 0x65bd3215
            animIdToAnimDataMap[animEndId] = self.createAnimationEvents(animation)

    def createAnimationEvents(self, animation):
        event = self.createInstanceOf("SDEV")
        event.frames = []
        event.flags = 1
        event.fend = self.frameToMS(animation.exlusiveEndFrame)
        event.keys = []

        if animation.useSimulateFrame:
            # TODO: does the flag matter?
            event.flags = 0
            event.frames.append(self.frameToMS(animation.simulateFrame))
            event.keys.append(self.createSimulateEventKey())

        event.frames.append(self.frameToMS(animation.exlusiveEndFrame))
        event.keys.append(self.createAnimationEndEventKey())

        return event

    def createAnimationEndEventKey(self):
        event = self.createInstanceOf("EVNT")
        event.name = "Evt_SeqEnd"
        event.matrix = self.createIdentityMatrix()
        return event

    def createSimulateEventKey(self):
        event = self.createInstanceOf("EVNT")
        event.name = "Evt_Simulate"
        # link boneIndex to a bone that matches event name
        # no idea if this matters but that's what Blizzard models do
        event.boneIndex = self.boneNameToBoneIndexMap.get(event.name, -1)
        event.matrix = self.createIdentityMatrix()
        # TODO: does the matrix matter? do the unknown fields matter?
        return event

    def initWithPreparedAnimationData(self, model):
        self.animIdListToSTSIndexMap = {}
        for animationIndex in self.animationIndicesToExport:
            animation = self.scene.m3_animations[animationIndex]
            animIdToAnimDataMap = self.nameToAnimIdToAnimDataMap[animation.name]
            animIds = list(animIdToAnimDataMap.keys())
            animIds.sort()

            m3Sequence = self.createInstanceOf("SEQS")
            m3Sequence.animStartInMS = self.frameToMS(animation.startFrame)
            m3Sequence.animEndInMS = self.frameToMS(animation.exlusiveEndFrame)
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Sequence, blenderObject=animation, animPathPrefix=None, rootObject=self.scene)
            m3Sequence.name = animation.name
            shared.transferAnimation(transferer)
            m3Sequence.boundingSphere = self.createAlmostEmptyBoundingsWithRadius(2)
            model.sequences.append(m3Sequence)

            m3SequenceTransformationGroup = self.createInstanceOf("STG_")
            m3SequenceTransformationGroup.name = animation.name
            model.sequenceTransformationGroups.append(m3SequenceTransformationGroup)

            remainingIds = set(animIds)

            fullM3STC = None
            for stcIndex, stc in enumerate(animation.transformationCollections):
                # no check for duplicate names is necessary:
                # there are models with duplicate names
                animIdsOfSTC = list()

                for animatedProperty in stc.animatedProperties:
                    longAnimId = animatedProperty.longAnimId
                    animId = self.getAnimIdForLongAnimId(longAnimId)
                    if animId in remainingIds:
                        remainingIds.remove(animId)
                        animIdsOfSTC.append(animId)

                animIdsOfSTC.sort()

                stcIndex = len(model.sequenceTransformationCollections)
                m3SequenceTransformationGroup.stcIndices.append(stcIndex)
                m3STC = self.createInstanceOf("STC_")
                m3STC.name = animation.name + "_" + stc.name
                m3STC.animIds = animIdsOfSTC
                model.sequenceTransformationCollections.append(m3STC)

                transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3STC, blenderObject=stc, animPathPrefix=None, rootObject=self.scene)
                shared.transferSTC(transferer)

                for animId in m3STC.animIds:
                    animData = animIdToAnimDataMap[animId]
                    self.addAnimDataToTransformCollection(animData, m3STC)

                if stc.name == "full":
                    fullM3STC = m3STC

            if fullM3STC is None:
                stcIndex = len(model.sequenceTransformationCollections)
                m3SequenceTransformationGroup.stcIndices.append(stcIndex)
                fullM3STC = self.createInstanceOf("STC_")
                fullM3STC.name = animation.name + "_" + "full"
                model.sequenceTransformationCollections.append(fullM3STC)

            fullM3STC.animIds.extend(remainingIds)
            for animId in remainingIds:
                animData = animIdToAnimDataMap[animId]
                self.addAnimDataToTransformCollection(animData, fullM3STC)

            for m3STC in model.sequenceTransformationCollections:
                m3STC.stsIndex = self.getSTSIndexFor(model, m3STC.animIds)
                m3STC.stsIndexCopy = m3STC.stsIndex

    def getSTSIndexFor(self, model, animIds):
        animIdsSorted = list(animIds)
        animIdsSorted.sort()
        animIdsTuple = tuple(animIdsSorted)
        stsIndex = self.animIdListToSTSIndexMap.get(animIdsTuple)
        if stsIndex is None:
            stsIndex = len(model.sts)
            m3STS = self.createInstanceOf("STS_")
            m3STS.animIds = list(animIds)
            model.sts.append(m3STS)
            self.animIdListToSTSIndexMap[animIdsTuple] = stsIndex
        return stsIndex

    def addAnimDataToTransformCollection(self, animData, m3SequenceTransformationCollection):
        animDataType = animData.structureDescription.structureName
        if animDataType == "SDEV":
            sdevIndex = len(m3SequenceTransformationCollection.sdev)
            m3SequenceTransformationCollection.sdev.append(animData)
            # sdev's have animation type index 0, so sdevIndex = animRef
            animRef = sdevIndex
        elif animDataType == "SD2V":
            sd2vIndex = len(m3SequenceTransformationCollection.sd2v)
            m3SequenceTransformationCollection.sd2v.append(animData)
            animRef = 0x10000 + sd2vIndex
        elif animDataType == "SD3V":
            sd3vIndex = len(m3SequenceTransformationCollection.sd3v)
            m3SequenceTransformationCollection.sd3v.append(animData)
            animRef = 0x20000 + sd3vIndex
        elif animDataType == "SD4Q":
            sd4qIndex = len(m3SequenceTransformationCollection.sd4q)
            m3SequenceTransformationCollection.sd4q.append(animData)
            animRef = 0x30000 + sd4qIndex
        elif animDataType == "SDCC":
            sdccIndex = len(m3SequenceTransformationCollection.sdcc)
            m3SequenceTransformationCollection.sdcc.append(animData)
            animRef = 0x40000 + sdccIndex
        elif animDataType == "SDR3":
            sdr3Index = len(m3SequenceTransformationCollection.sdr3)
            m3SequenceTransformationCollection.sdr3.append(animData)
            animRef = 0x50000 + sdr3Index
        elif animDataType == "SDS6":
            sds6Index = len(m3SequenceTransformationCollection.sds6)
            m3SequenceTransformationCollection.sds6.append(animData)
            animRef = 0x70000 + sds6Index
        elif animDataType == "SDU6":
            sdu6Index = len(m3SequenceTransformationCollection.sdu6)
            m3SequenceTransformationCollection.sdu6.append(animData)
            animRef = 0x80000 + sdu6Index
        elif animDataType == "SDU3":
            sdu3Index = len(m3SequenceTransformationCollection.sdu3)
            m3SequenceTransformationCollection.sdu3.append(animData)
            animRef = 0xa0000 + sdu3Index
        elif animDataType == "SDFG":
            sdfgIndex = len(m3SequenceTransformationCollection.sdfg)
            m3SequenceTransformationCollection.sdfg.append(animData)
            animRef = 0xb0000 + sdfgIndex
        elif animDataType == "SDMB":
            sdmbIndex = len(m3SequenceTransformationCollection.sdmb)
            m3SequenceTransformationCollection.sdmb.append(animData)
            animRef = 0xc0000 + sdmbIndex
        else:
            raise Exception("Can't handle animation data of type %s yet" % animDataType)
        m3SequenceTransformationCollection.animRefs.append(animRef)

    def initCameras(self, model):
        scene = self.scene
        for cameraIndex, camera in enumerate(scene.m3_cameras):
            m3Camera = self.createInstanceOf("CAM_")
            boneName = camera.name
            boneIndex = self.boneNameToBoneIndexMap.get(boneName)
            if boneIndex is None:
                boneIndex = self.addBoneWithRestPosAndReturnIndex(model, boneName, realBone=False)
            m3Camera.boneIndex = boneIndex
            m3Camera.name = camera.name
            animPathPrefix = "m3_cameras[%s]." % cameraIndex
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Camera, blenderObject=camera, animPathPrefix=animPathPrefix, rootObject=self.scene)
            shared.transferCamera(transferer)
            model.cameras.append(m3Camera)

    def initTighHitTest(self, model):
        scene = self.scene
        model.tightHitTest = self.createSSGS(scene.m3_tight_hit_test, fixedName=shared.tightHitTestBoneName)

    def initFuzzyHitTests(self, model):
        scene = self.scene
        for fuzzyHitTest in scene.m3_fuzzy_hit_tests:
            m3FuzzyHitTest = self.createSSGS(fuzzyHitTest)
            model.fuzzyHitTestObjects.append(m3FuzzyHitTest)

    def createSSGS(self, shapeObject, fixedName=None):
        m3ShapeObject = self.createInstanceOf("SSGS")
        if fixedName is not None:
            boneName = fixedName
        else:
            boneName = shapeObject.boneName
        boneIndex = self.boneNameToBoneIndexMap.get(boneName, -1)
        m3ShapeObject.boneIndex = boneIndex
        transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3ShapeObject, blenderObject=shapeObject, animPathPrefix=None, rootObject=self.scene)
        shared.transferFuzzyHitTest(transferer)
        matrix = shared.composeMatrix(shapeObject.offset, shapeObject.rotationEuler, shapeObject.scale)
        m3ShapeObject.matrix = self.createMatrixFromBlenderMatrix(matrix)
        return m3ShapeObject

    def initParticles(self, model):
        scene = self.scene

        particleSystemNameToIndexMap = {}
        for particleSystemIndex, particleSystem in enumerate(scene.m3_particle_systems):
            particleSystemNameToIndexMap[particleSystem.name] = particleSystemIndex

        for particleSystemIndex, particleSystem in enumerate(scene.m3_particle_systems):
            boneName = particleSystem.boneName
            boneIndex = self.boneNameToBoneIndexMap.get(boneName)
            if boneIndex is None:
                boneIndex = self.addBoneWithRestPosAndReturnIndex(model, boneName, realBone=False)
            m3ParticleSystem = self.createInstanceOf("PAR_")
            m3ParticleSystem.boneIndex = boneIndex
            animPathPrefix = "m3_particle_systems[%s]." % particleSystemIndex
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3ParticleSystem, blenderObject=particleSystem, animPathPrefix=animPathPrefix, rootObject=self.scene)
            shared.transferParticleSystem(transferer)
            m3ParticleSystem.indexPlusHighestIndex = len(scene.m3_particle_systems) - 1 + particleSystemIndex
            m3ParticleSystem.setNamedBit("flags", "smoothSize", particleSystem.sizeSmoothingType == "1")
            m3ParticleSystem.setNamedBit("flags", "smoothColor", particleSystem.colorSmoothingType == "1")
            m3ParticleSystem.setNamedBit("flags", "smoothRotation", particleSystem.rotationSmoothingType == "1")
            m3ParticleSystem.setNamedBit("flags", "bezSmoothSize", particleSystem.sizeSmoothingType in ["2", "4"])
            m3ParticleSystem.setNamedBit("flags", "bezSmoothColor", particleSystem.colorSmoothingType in ["2", "4"])
            m3ParticleSystem.setNamedBit("flags", "bezSmoothRotation", particleSystem.rotationSmoothingType in ["2", "4"])
            m3ParticleSystem.unknowne0bd54c8 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknowna2d44d80 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknownf8e2b3d0 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknown54f4ae30 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknown5f54fb02 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknown84d843d6 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknown9cb3dd18 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknown2e01be90 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknownf6193fc0 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknowna5e2260a = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknown485f7eea = self.createNullAnimHeader(interpolationType=0)
            m3ParticleSystem.unknown34b6f141 = self.createNullAnimHeader(interpolationType=0)
            m3ParticleSystem.unknown89cdf966 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknown4eefdfc1 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3ParticleSystem.unknownab37a1d5 = self.createNullAnimHeader(interpolationType=1)
            m3ParticleSystem.unknownbef7f4d3 = self.createNullAnimHeader(interpolationType=1)
            m3ParticleSystem.unknownb2dbf2f3 = self.createNullAnimHeader(interpolationType=1)
            m3ParticleSystem.unknown3c76d64c = self.createNullAnimHeader(interpolationType=1)
            m3ParticleSystem.unknownbc151e17 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            if self.getVersionOf("PAR_") >= 21:
                m3ParticleSystem.unknown8f507b52 = self.createNullAnimHeader(interpolationType=1)
                m3ParticleSystem.unknown22856fde = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
                m3ParticleSystem.unknownb35ad6e1 = self.createNullVector2AnimationReference(x=0.0, y=0.0, interpolationType=1)
                m3ParticleSystem.unknown686e5943 = self.createNullVector3AnimationReference(x=0.0, y=0.0, z=0.0, initIsNullValue=False, interpolationType=1)
                m3ParticleSystem.unknown18a90564 = self.createNullVector2AnimationReference(x=0.0, y=0.0, interpolationType=1)
            m3ParticleSystem.unknown21ca0cea = self.createNullAnimHeader(interpolationType=1)
            m3ParticleSystem.unknown1e97145f = self.createNullFloatAnimationReference(initValue=1.0, nullValue=0.0)
            model.particles.append(m3ParticleSystem)

            materialReferenceIndex = self.materialNameToNewReferenceIndexMap.get(particleSystem.materialName)
            if materialReferenceIndex is None:
                raise ExportError("The particle system %s uses '%s' as material, but no m3 material with that name exist!" % (particleSystem.name, particleSystem.materialName))
            m3ParticleSystem.materialReferenceIndex = materialReferenceIndex
            m3ParticleSystem.worldForceChannelsCopy = m3ParticleSystem.worldForceChannels
            m3ParticleSystem.trailingParticlesIndex = particleSystemNameToIndexMap.get(particleSystem.trailingParticlesName, -1)
            if m3ParticleSystem.trailingParticlesIndex == -1 and particleSystem.trailingParticlesName != "":
                raise ExportError("The particle system %s has configured a particle system called %s as trailing parameters but it does not exist." % (particleSystem.name, m3ParticleSystem.trailingParticlesName))

            for spawnPointIndex, spawnPoint in enumerate(particleSystem.spawnPoints):
                m3SpawnPoint = self.createInstanceOf("SVC3")
                spawnPointAnimPathPrefix = animPathPrefix + "spawnPoints[%d]." % spawnPointIndex
                transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3SpawnPoint, blenderObject=spawnPoint, animPathPrefix=spawnPointAnimPathPrefix, rootObject=self.scene)
                shared.transferSpawnPoint(transferer)
                m3ParticleSystem.spawnPoints.append(m3SpawnPoint)
            for blenderCopyIndex, copy in enumerate(particleSystem.copies):
                m3Copy = self.createInstanceOf("PARC")
                boneName = copy.boneName
                boneIndex = self.boneNameToBoneIndexMap.get(boneName)
                if boneIndex is None:
                    boneIndex = self.addBoneWithRestPosAndReturnIndex(model, boneName, realBone=False)
                m3Copy.boneIndex = boneIndex
                copyAnimPathPrefix = animPathPrefix + "copies[%d]." % blenderCopyIndex
                transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Copy, blenderObject=copy, animPathPrefix=copyAnimPathPrefix, rootObject=self.scene)
                shared.transferParticleSystemCopy(transferer)
                copyIndex = len(model.particleCopies)
                model.particleCopies.append(m3Copy)
                m3ParticleSystem.copyIndices.append(copyIndex)

    def initRibbons(self, model):
        scene = self.scene
        for ribbonIndex, ribbon in enumerate(scene.m3_ribbons):
            boneName = ribbon.boneName
            boneIndex = self.boneNameToBoneIndexMap.get(boneName)
            if boneIndex is None:
                boneIndex = self.addBoneWithRestPosAndReturnIndex(model, boneName, realBone=False)
            m3Ribbon = self.createInstanceOf("RIB_")
            m3Ribbon.boneIndex = boneIndex
            animPathPrefix = "m3_ribbons[%s]." % ribbonIndex
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Ribbon, blenderObject=ribbon, animPathPrefix=animPathPrefix, rootObject=self.scene)
            shared.transferRibbon(transferer)

            m3Ribbon.unknownee00ae0a = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3Ribbon.unknown1686c0b7 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3Ribbon.unknown9eba8df8 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)

            if len(ribbon.endPoints) == 0:
                m3Ribbon.localForceChannelsCopy = m3Ribbon.localForceChannels
                m3Ribbon.worldForceChannelsCopy = m3Ribbon.worldForceChannels

            model.ribbons.append(m3Ribbon)

            materialReferenceIndex = self.materialNameToNewReferenceIndexMap.get(ribbon.materialName)
            if materialReferenceIndex is None:
                raise ExportError("The ribbon %s uses '%s' as material, but no m3 material with that name exist!" % (ribbon.name, ribbon.materialName))
            m3Ribbon.materialReferenceIndex = materialReferenceIndex

            for ii, endPoint in enumerate(ribbon.endPoints):
                m3EndPoint = self.createInstanceOf("SRIB")
                boneName = endPoint.name
                boneIndex = self.boneNameToBoneIndexMap.get(boneName)
                if boneIndex is None:
                    raise ExportError("The bone %s of an end point from ribbon %s does not exist" % (boneName, ribbon.name))
                m3EndPoint.boneIndex = boneIndex

                endPointAnimPathPrefix = animPathPrefix + "endPoints[%d]." % ii
                transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3EndPoint, blenderObject=endPoint, animPathPrefix=endPointAnimPathPrefix, rootObject=self.scene)
                shared.transferRibbonEndPoint(transferer)

                m3EndPoint.unknown3 = self.createNullFloatAnimationReference(initValue=1.0, nullValue=0.0)
                m3EndPoint.unknown4 = self.createNullFloatAnimationReference(initValue=1.0, nullValue=0.0)

                m3Ribbon.endPoints.append(m3EndPoint)

    def initProjections(self, model):
        scene = self.scene
        for projectionIndex, projection in enumerate(scene.m3_projections):
            boneName = projection.boneName
            boneIndex = self.boneNameToBoneIndexMap.get(boneName)
            if boneIndex is None:
                boneIndex = self.addBoneWithRestPosAndReturnIndex(model, boneName, realBone=False)
            m3Projection = self.createInstanceOf("PROJ")
            m3Projection.boneIndex = boneIndex

            animPathPrefix = "m3_projections[%s]." % projectionIndex
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Projection, blenderObject=projection, animPathPrefix=animPathPrefix, rootObject=self.scene)
            shared.transferProjection(transferer)

            m3Projection.boxBottomZOffset = self.createNullFloatAnimationReference(initValue=(- projection.depth / 2.0), nullValue=0.0)
            m3Projection.boxTopZOffset = self.createNullFloatAnimationReference(initValue=(projection.depth / 2.0), nullValue=0.0)
            m3Projection.boxLeftXOffset = self.createNullFloatAnimationReference(initValue=(- projection.width / 2.0), nullValue=0.0)
            m3Projection.boxRightXOffset = self.createNullFloatAnimationReference(initValue=(projection.width / 2.0), nullValue=0.0)
            m3Projection.boxFrontYOffset = self.createNullFloatAnimationReference(initValue=(- projection.height / 2.0), nullValue=0.0)
            m3Projection.boxBackYOffset = self.createNullFloatAnimationReference(initValue=(projection.height / 2.0), nullValue=0.0)

            m3Projection.unknownf1f7110b = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3Projection.unknown2035f500 = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3Projection.unknown80d8189b = self.createNullFloatAnimationReference(initValue=0.0, nullValue=0.0)
            m3Projection.unknown58ae2b94 = self.createNullVector3AnimationReference(x=0.0, y=0.0, z=0.0, initIsNullValue=False, interpolationType=1)

            materialReferenceIndex = self.materialNameToNewReferenceIndexMap.get(projection.materialName)
            if materialReferenceIndex is None:
                raise ExportError("The projection %s uses '%s' as material, but no m3 material with that name exist!" % (projection.name, projection.materialName))
            m3Projection.materialReferenceIndex = materialReferenceIndex

            model.projections.append(m3Projection)

    def initWarps(self, model):
        scene = self.scene
        for warpIndex, warp in enumerate(scene.m3_warps):
            boneName = warp.boneName
            boneIndex = self.boneNameToBoneIndexMap.get(boneName)
            if boneIndex is None:
                boneIndex = self.addBoneWithRestPosAndReturnIndex(model, boneName, realBone=False)
            m3Warp = self.createInstanceOf("WRP_")
            m3Warp.bone = boneIndex
            animPathPrefix = "m3_warps[%s]." % warpIndex
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Warp, blenderObject=warp, animPathPrefix=animPathPrefix, rootObject=self.scene)
            shared.transferWarp(transferer)
            model.warps.append(m3Warp)

    def initForces(self, model):
        scene = self.scene
        for forceIndex, force in enumerate(scene.m3_forces):
            boneName = force.boneName
            boneIndex = self.boneNameToBoneIndexMap.get(boneName)
            if boneIndex is None:
                boneIndex = self.addBoneWithRestPosAndReturnIndex(model, boneName, realBone=False)
            m3Force = self.createInstanceOf("FOR_")
            m3Force.boneIndex = boneIndex
            animPathPrefix = "m3_forces[%s]." % forceIndex
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Force, blenderObject=force, animPathPrefix=animPathPrefix, rootObject=self.scene)
            shared.transferForce(transferer)
            model.forces.append(m3Force)

    def initPhysicsMesh(self, physicsShape, m3PhysicsShape):
        scene = self.scene
        meshObject = scene.objects[physicsShape.meshObjectName]
        if meshObject is None:
            print("Warning: No mesh object %s found in scene for physics shape: %s" % physicsShape.meshObjectName, physicsShape.name)
            return

        mesh = meshObject.data
        vertices = [v.co for v in mesh.vertices]
        faces = [f.vertices for f in mesh.polygons]
        triFaces = []
        for f in faces:
            if len(f) == 3:
                triFaces.append(f)
            elif len(f) == 4:
                triFaces.append([f[0], f[1], f[2]])
                triFaces.append([f[2], f[3], f[0]])
            else:
                print("Warning: Only triangles / quads are supported for physics meshes.")
                return

        faceIndices = [i for f in triFaces for i in f]

        for v in vertices:
            m3PhysicsShape.vertices.append(self.createVector3(v[0], v[1], v[2]))

        m3PhysicsShape.faces.extend(faceIndices)

    def initRigidBodies(self, model):
        scene = self.scene
        for rigidBodyIndex, rigidBody in enumerate(scene.m3_rigid_bodies):
            self.operator.report({'WARNING'}, 'M3Export: Attempting to export rigid body "%s". This might corrupt the model and crash the game.' % rigidBody.name)
            boneName = rigidBody.name
            boneIndex = self.boneNameToBoneIndexMap.get(boneName)
            if boneIndex is None:
                boneIndex = self.addBoneWithRestPosAndReturnIndex(model, boneName, realBone=False)
            m3RigidBody = self.createInstanceOf("PHRB")
            m3RigidBody.boneIndex = boneIndex
            animPathPrefix = "m3_rigid_bodies[%s]." % rigidBodyIndex
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3RigidBody, blenderObject=rigidBody, animPathPrefix=animPathPrefix, rootObject=self.scene)
            shared.transferRigidBody(transferer)

            for physicsShapeIndex, physicsShape in enumerate(rigidBody.physicsShapes):
                m3PhysicsShape = self.createInstanceOf("PHSH")
                animPathPrefix = "m3_physics_shapes[%s]." % physicsShapeIndex
                transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3PhysicsShape, blenderObject=physicsShape, animPathPrefix=animPathPrefix, rootObject=self.scene)
                shared.transferPhysicsShape(transferer)
                matrix = shared.composeMatrix(physicsShape.offset, physicsShape.rotationEuler, physicsShape.scale)
                m3PhysicsShape.matrix = self.createMatrixFromBlenderMatrix(matrix)

                if physicsShape.shape in ["4", "5"]:
                    self.initPhysicsMesh(physicsShape, m3PhysicsShape)
                    # TODO: bounding planes?

                m3RigidBody.physicsShapes.append(m3PhysicsShape)

            model.rigidBodies.append(m3RigidBody)

    def initLights(self, model):
        scene = self.scene
        for lightIndex, light in enumerate(scene.m3_lights):
            boneName = light.boneName
            boneIndex = self.boneNameToBoneIndexMap.get(boneName)
            if boneIndex is None:
                boneIndex = self.addBoneWithRestPosAndReturnIndex(model, boneName, realBone=False)
            m3Light = self.createInstanceOf("LITE")
            m3Light.boneIndex = boneIndex
            animPathPrefix = "m3_lights[%s]." % lightIndex
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Light, blenderObject=light, animPathPrefix=animPathPrefix, rootObject=self.scene)
            shared.transferLight(transferer)
            model.lights.append(m3Light)

    def initBillboardBehaviors(self, model):
        scene = self.scene
        for billboardBehaviorIndex, billboardBehavior in enumerate(scene.m3_billboard_behaviors):
            boneName = billboardBehavior.name
            boneIndex = self.boneNameToBoneIndexMap.get(boneName)
            # Export only if used:
            if boneIndex is not None:
                m3BillboardBehavior = self.createInstanceOf("BBSC")
                m3BillboardBehavior.boneIndex = boneIndex
                animPathPrefix = "m3_billboard_behaviors[%s]." % billboardBehaviorIndex
                transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3BillboardBehavior, blenderObject=billboardBehavior, animPathPrefix=animPathPrefix, rootObject=self.scene)
                shared.transferBillboardBehavior(transferer)
                model.billboardBehaviors.append(m3BillboardBehavior)

    def initIkChains(self, model):
        scene = self.scene
        for ikChainIndex, ikChain in enumerate(scene.m3_ik_chains):
            boneName1 = ikChain.boneName1
            boneName2 = ikChain.boneName2
            boneIndex1 = self.boneNameToBoneIndexMap.get(boneName1)
            boneIndex2 = self.boneNameToBoneIndexMap.get(boneName2)
            # Export only if used:
            if boneIndex1 is not None or boneIndex2 is not None:
                m3IkChain = self.createInstanceOf("IKJT")
                m3IkChain.boneIndex1 = boneIndex1
                m3IkChain.boneIndex2 = boneIndex2
                animPathPrefix = "m3_ik_chains[%s]." % ikChainIndex
                transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3IkChain, blenderObject=ikChain, animPathPrefix=animPathPrefix, rootObject=self.scene)
                shared.transferIkChain(transferer)
                model.inverseKinematicChains.append(m3IkChain)
            else:
                print("m3_ik_chains[%s] contains incorrect bone reference" % ikChainIndex)

    def initTurretBehaviors(self, model):
        scene = self.scene
        for ii, turret in enumerate(scene.m3_turret_behaviors):
            m3TurretBehavior = self.createInstanceOf("TRGD")
            m3TurretBehavior.name = turret.name

            # There must only be one part per turret behavior that is marked as the main bone
            # It should also be before the other parts of the turret behavior in the model's PATU reference list
            hasMainTurretBone = False
            for jj, part in enumerate(turret.parts):
                if hasMainTurretBone:
                    part.mainTurretBone = False
                elif part.mainTurretBone:
                    turret.parts.move(jj, 0)
                    hasMainTurretBone = True

            for jj, part in enumerate(turret.parts):
                m3TurretBehaviorPart = self.createInstanceOf("PATU")
                m3TurretBehaviorPart.boneIndex = self.boneNameToBoneIndexMap.get(part.name)

                animPathPrefix = "m3_turret_behaviors[%s].parts[%s]" % (ii, jj)
                transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3TurretBehaviorPart, blenderObject=part, animPathPrefix=animPathPrefix, rootObject=self.scene)
                shared.transferTurretBehaviorPart(transferer)

                m3TurretBehaviorPart.forwardX.x = part.forwardX[0]
                m3TurretBehaviorPart.forwardX.y = part.forwardX[1]
                m3TurretBehaviorPart.forwardX.z = part.forwardX[2]
                m3TurretBehaviorPart.forwardX.w = part.forwardX[3]
                m3TurretBehaviorPart.forwardY.x = part.forwardY[0]
                m3TurretBehaviorPart.forwardY.y = part.forwardY[1]
                m3TurretBehaviorPart.forwardY.z = part.forwardY[2]
                m3TurretBehaviorPart.forwardY.w = part.forwardY[3]
                m3TurretBehaviorPart.forwardZ.x = part.forwardZ[0]
                m3TurretBehaviorPart.forwardZ.y = part.forwardZ[1]
                m3TurretBehaviorPart.forwardZ.z = part.forwardZ[2]
                m3TurretBehaviorPart.forwardZ.w = part.forwardZ[3]
                m3TurretBehaviorPart.upX.x = part.upX[0]
                m3TurretBehaviorPart.upX.y = part.upX[1]
                m3TurretBehaviorPart.upX.z = part.upX[2]
                m3TurretBehaviorPart.upX.w = part.upX[3]
                m3TurretBehaviorPart.upY.x = part.upY[0]
                m3TurretBehaviorPart.upY.y = part.upY[1]
                m3TurretBehaviorPart.upY.z = part.upY[2]
                m3TurretBehaviorPart.upY.w = part.upY[3]
                m3TurretBehaviorPart.upZ.x = part.upZ[0]
                m3TurretBehaviorPart.upZ.y = part.upZ[1]
                m3TurretBehaviorPart.upZ.z = part.upZ[2]
                m3TurretBehaviorPart.upZ.w = part.upZ[3]

                m3TurretBehavior.partIndex.append(len(model.turretBehaviorParts))
                model.turretBehaviorParts.append(m3TurretBehaviorPart)

            model.turretBehaviors.append(m3TurretBehavior)

    def initPhysicsJoints(self, model):
        scene = self.scene
        for ii, pj in enumerate(scene.m3_physics_joints):
            boneName1 = pj.boneName1
            boneName2 = pj.boneName2
            boneIndex1 = self.boneNameToBoneIndexMap.get(boneName1)
            boneIndex2 = self.boneNameToBoneIndexMap.get(boneName2)

            if boneIndex1 is None:
                boneIndex1 = self.addBoneWithRestPosAndReturnIndex(model, boneName1, realBone=True)

            if boneIndex2 is None:
                boneIndex2 = self.addBoneWithRestPosAndReturnIndex(model, boneName2, realBone=True)

            m3pj = self.createInstanceOf("PHYJ")
            m3pj.boneIndex1 = boneIndex1
            m3pj.boneIndex2 = boneIndex2
            matrix = shared.composeMatrix(pj.offset1, pj.rotation1, [1, 1, 1])
            m3pj.matrix1 = self.createMatrixFromBlenderMatrix(matrix)
            matrix = shared.composeMatrix(pj.offset2, pj.rotation2, [1, 1, 1])
            m3pj.matrix2 = self.createMatrixFromBlenderMatrix(matrix)

            animPathPrefix = "m3_physics_joints[%s]." % ii
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3pj, blenderObject=pj, animPathPrefix=animPathPrefix, rootObject=self.scene)
            shared.transferPhysicsJoint(transferer)
            model.physicsJoints.append(m3pj)

    def initAttachmentPoints(self, model):
        scene = self.scene
        for attachmentPointIndex, attachmentPoint in enumerate(scene.m3_attachment_points):
            boneName = attachmentPoint.boneName
            boneIndex = self.boneNameToBoneIndexMap.get(boneName)
            if boneIndex is None:
                boneIndex = self.addBoneWithRestPosAndReturnIndex(model, boneName, realBone=True)
            m3AttachmentPoint = self.createInstanceOf("ATT_")
            m3AttachmentPoint.name = shared.attachmentPointPrefix + attachmentPoint.name
            m3AttachmentPoint.boneIndex = boneIndex
            model.attachmentPoints.append(m3AttachmentPoint)
            model.attachmentPointAddons.append(0xffff)

            if attachmentPoint.volumeType != "-1":
                m3AttachmentVolume = self.createInstanceOf("ATVL")
                m3AttachmentVolume.bone0 = boneIndex
                m3AttachmentVolume.bone1 = boneIndex
                m3AttachmentVolume.bone2 = boneIndex
                m3AttachmentVolume.type = int(attachmentPoint.volumeType)
                m3AttachmentVolume.size0 = attachmentPoint.volumeSize0
                m3AttachmentVolume.size1 = attachmentPoint.volumeSize1
                m3AttachmentVolume.size2 = attachmentPoint.volumeSize2
                m3AttachmentVolume.matrix = self.createIdentityMatrix()
                model.attachmentVolumes.append(m3AttachmentVolume)
                model.attachmentVolumesAddon0.append(0)
                model.attachmentVolumesAddon1.append(0)

    def toM3ColorComponent(self, blenderColorComponent):
        return sorted((0, round(blenderColorComponent * 255), 255))[1]

    def toM3Color(self, blenderColor):
        color = self.createInstanceOf("COL")
        color.red = self.toM3ColorComponent(blenderColor[0])
        color.green = self.toM3ColorComponent(blenderColor[1])
        color.blue = self.toM3ColorComponent(blenderColor[2])
        color.alpha = self.toM3ColorComponent(blenderColor[3])
        return color

    def createNullVector4As4uint8(self):
        vec = self.createInstanceOf("Vector4As4uint8")
        vec.x = 0
        vec.y = 0
        vec.z = 0
        vec.w = 0
        return vec

    def createMatrixFromBlenderMatrix(self, blenderMatrix):
        matrix = self.createInstanceOf("Matrix44")
        matrix.x = self.createVector4FromBlenderVector(blenderMatrix.col[0])
        matrix.y = self.createVector4FromBlenderVector(blenderMatrix.col[1])
        matrix.z = self.createVector4FromBlenderVector(blenderMatrix.col[2])
        matrix.w = self.createVector4FromBlenderVector(blenderMatrix.col[3])
        return matrix

    def createRestPositionFromBlender4x4Matrix(self, blenderMatrix):
        iref = self.createInstanceOf("IREF")
        iref.matrix = self.createMatrixFromBlenderMatrix(blenderMatrix)
        return iref

    def createIdentityRestPosition(self):
        iref = self.createInstanceOf("IREF")
        iref.matrix = self.createIdentityMatrix()
        return iref

    def createStaticBoneAtOrigin(self, name, realBone):
        m3Bone = self.createInstanceOf("BONE")
        m3Bone.name = name
        m3Bone.flags = 0
        m3Bone.setNamedBit("flags", "real", realBone)
        m3Bone.parent = -1
        m3Bone.location = self.createNullVector3AnimationReference(0.0, 0.0, 0.0, initIsNullValue=True)
        m3Bone.rotation = self.createNullQuaternionAnimationReference(x=0.0, y=0.0, z=0.0, w=1.0)
        m3Bone.scale = self.createNullVector3AnimationReference(1.0, 1.0, 1.0, initIsNullValue=True)
        m3Bone.ar1 = self.createNullUInt32AnimationReference(1)
        return m3Bone

    def initMaterials(self, model):
        scene = self.scene

        for oldReferenceIndex in self.oldReferenceIndicesInCorrectedOrder:
            materialReference = self.scene.m3_material_references[oldReferenceIndex]
            materialType = materialReference.materialType
            materialIndex = materialReference.materialIndex
            material = cm.getMaterial(scene, materialType, materialIndex)
            if material is None:
                raise ExportError("The material list contains an unsupported material of type %s" % shared.materialNames[materialType])
            model.materialReferences.append(self.createMaterialReference(materialIndex, materialType))

        if len(scene.m3_volume_noise_materials) > 0 and self.structureVersionMap["MODL"] < 25:
            materialNames = [*map(lambda x: x.name, scene.m3_volume_noise_materials)]
            raise ExportErrorMODLVersionInsufficient(25, f'Volume noise materials: {materialNames}')

        if len(scene.m3_stb_materials) > 0 and self.structureVersionMap["MODL"] < 26:
            materialNames = [*map(lambda x: x.name, scene.m3_stb_materials)]
            raise ExportErrorMODLVersionInsufficient(26, f'Splat terrain bake materials: {materialNames}')

        if len(scene.m3_lens_flare_materials) > 0 and self.structureVersionMap["MODL"] < 29:
            materialNames = [*map(lambda x: x.name, scene.m3_lens_flare_materials)]
            raise ExportErrorMODLVersionInsufficient(29, f'Lens flare materials: {materialNames}')

        if len(scene.m3_buffer_materials) > 0:
            materialNames = [*map(lambda x: x.name, scene.m3_buffer_materials)]
            raise ExportError(f'MADD based materials cannot be exported. Affected materials: {materialNames}')

        for materialIndex, material in enumerate(scene.m3_standard_materials):
            model.standardMaterials.append(self.createStandardMaterial(materialIndex, material))

        for materialIndex, material in enumerate(scene.m3_displacement_materials):
            model.displacementMaterials.append(self.createDisplacementMaterial(materialIndex, material))

        for materialIndex, material in enumerate(scene.m3_composite_materials):
            model.compositeMaterials.append(self.createCompositeMaterial(materialIndex, material))

        for materialIndex, material in enumerate(scene.m3_terrain_materials):
            model.terrainMaterials.append(self.createTerrainMaterial(materialIndex, material))

        for materialIndex, material in enumerate(scene.m3_volume_materials):
            model.volumeMaterials.append(self.createVolumeMaterial(materialIndex, material))

        for materialIndex, material in enumerate(scene.m3_creep_materials):
            model.creepMaterials.append(self.createCreepMaterial(materialIndex, material))

        for materialIndex, material in enumerate(scene.m3_volume_noise_materials):
            model.volumeNoiseMaterials.append(self.createVolumeNoiseMaterial(materialIndex, material))

        for materialIndex, material in enumerate(scene.m3_stb_materials):
            model.splatTerrainBakeMaterials.append(self.createSTBMaterial(materialIndex, material))

    def createMaterialLayer(self, layer, animPathPrefix):
        m3Layer = self.createInstanceOf("LAYR")
        transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Layer, blenderObject=layer, animPathPrefix=animPathPrefix, rootObject=self.scene)
        shared.transferMaterialLayer(transferer)
        m3Layer.brightness.nullValue = 1.0
        m3Layer.brightMult.nullValue = 1.0
        m3Layer.unknowna44bf452.nullValue = 1.0
        m3Layer.fresnelMaxOffset = layer.fresnelMax - layer.fresnelMin
        if m3Layer.structureDescription.structureVersion >= 25:
            m3Layer.fresnelInvertedMaskX = 1.0 - layer.fresnelMaskX
            m3Layer.fresnelInvertedMaskY = 1.0 - layer.fresnelMaskY
            m3Layer.fresnelInvertedMaskZ = 1.0 - layer.fresnelMaskZ
        m3Layer.setNamedBit("flags", "useParticleFlipBook", layer.uvSource == "6")
        isVideo = shared.isVideoFilePath(layer.imagePath)
        m3Layer.setNamedBit("flags", "isVideo", isVideo)
        if not isVideo:
            m3Layer.vidoeFrameRate = 0
            m3Layer.videoStartFrame = 0
            m3Layer.videoEndFrame = 0
            m3Layer.videoMode = 0
        m3Layer.unknownbc0c14e5 = self.createNullUInt32AnimationReference(0)
        m3Layer.unknowne740df12 = self.createNullFloatAnimationReference(0.0, interpolationType=1)
        m3Layer.unknown39ade219 = self.createNullUInt16AnimationReference(0)
        m3Layer.unknowna4ec0796 = self.createNullUInt32AnimationReference(0, interpolationType=1)
        m3Layer.unknowna44bf452 = self.createNullFloatAnimationReference(1.0, interpolationType=1)
        return m3Layer

    def indexOfNameInCollection(self, name, collection):
        for index, element in enumerate(collection):
            if element.name == name:
                return index
        return -1

    def createMaterialLayers(self, material, m3Material, materialAnimPathPrefix):
        orderedListOfFieldNames = list(shared.layerFieldNamesOfM3Material(m3Material))

        orderedListOfLayerNames = list()
        for layerFieldName in orderedListOfFieldNames:
            layerName = shared.getLayerNameFromFieldName(layerFieldName)
            orderedListOfLayerNames.append(layerName)
        # Add mising layers. They get added for real since:
        # 1. this way animation ids can be saved for them
        # 2. New layers get added automatically that way
        layersAdded = False
        for layerName in orderedListOfLayerNames:
            if layerName not in material.layers:
                newLayer = material.layers.add()
                newLayer.name = layerName
                layersAdded = True
                print("Adding missing layer %s to material %s" % (layerName, material.name))

        layerIndicex = []
        for layerIndex, layer in enumerate(material.layers):
            if layer.name in orderedListOfLayerNames:
                layerIndicex.append(layerIndex)

        if layersAdded:
            # Sort the layers, so that the layers are
            # after an initial phase always at the same position.
            # This makes it easier to find layers in models of other players
            # Don't sort if no layer has been added -> downgrade situation
            for targetIndex, layerName in enumerate(orderedListOfLayerNames):
                currentIndex = self.indexOfNameInCollection(layerName, material.layers)
                if targetIndex != currentIndex:
                    material.layers.move(currentIndex, targetIndex)

        for layerIndex, layerFieldName, layerName in zip(layerIndicex, orderedListOfFieldNames, orderedListOfLayerNames):
            layer = material.layers[layerIndex]
            animPathPrefix = materialAnimPathPrefix + "layers[%s]." % layerIndex
            m3Layer = self.createMaterialLayer(layer, animPathPrefix)
            setattr(m3Material, layerFieldName, [m3Layer])

    def createStandardMaterial(self, materialIndex, material):
        m3Material = self.createInstanceOf("MAT_")
        materialAnimPathPrefix = "m3_standard_materials[%s]." % materialIndex
        transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Material, blenderObject=material, animPathPrefix=materialAnimPathPrefix, rootObject=self.scene)
        shared.transferStandardMaterial(transferer)
        m3Material.name = material.name
        self.createMaterialLayers(material, m3Material, materialAnimPathPrefix)

        for blenderMaterialLayer in material.layers:
            if blenderMaterialLayer.rttChannel != "-1":
                nameOfFlagToSet = "channel" + blenderMaterialLayer.rttChannel
                m3Material.setNamedBit("usedRTTChannels", nameOfFlagToSet, True)

        useDepthBlendFalloff = m3Material.getNamedBit("additionalFlags", "useDepthBlendFalloff")
        if not useDepthBlendFalloff:
            m3Material.depthBlendFalloff = 0.0

        useVertexColor = m3Material.getNamedBit("flags", "useVertexColor")
        useVertexAlpha = m3Material.getNamedBit("flags", "useVertexAlpha")

        usedByParticleSystem = False
        particleSystemUsesAlpha = False
        for particleSystem in self.scene.m3_particle_systems:
            if particleSystem.materialName == material.name:
                usedByParticleSystem = True
                if particleSystem.useVertexAlpha:
                    particleSystemUsesAlpha = True

        makesUseOfVertexColor = useVertexColor or usedByParticleSystem
        makesUseOfVertexAlpha = useVertexAlpha or particleSystemUsesAlpha

        m3Material.setNamedBit("additionalFlags", "makesUseOfVertexColor", makesUseOfVertexColor)
        m3Material.setNamedBit("additionalFlags", "makesUseOfVertexAlpha", makesUseOfVertexAlpha)

        m3Material.unknownAnimationRef2 = self.createNullUInt32AnimationReference(0)
        return m3Material

    def createDisplacementMaterial(self, materialIndex, material):
        m3Material = self.createInstanceOf("DIS_")
        materialAnimPathPrefix = "m3_displacement_materials[%s]." % materialIndex
        transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Material, blenderObject=material, animPathPrefix=materialAnimPathPrefix, rootObject=self.scene)
        shared.transferDisplacementMaterial(transferer)
        m3Material.name = material.name
        self.createMaterialLayers(material, m3Material, materialAnimPathPrefix)
        return m3Material

    def createCompositeMaterial(self, materialIndex, material):
        m3Material = self.createInstanceOf("CMP_")
        materialAnimPathPrefix = "m3_composite_materials[%s]." % materialIndex
        transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Material, blenderObject=material, animPathPrefix=materialAnimPathPrefix, rootObject=self.scene)
        shared.transferCompositeMaterial(transferer)
        m3Material.name = material.name
        for sectionIndex, section in enumerate(material.sections):
            m3Section = self.createInstanceOf("CMS_")
            m3Section.materialReferenceIndex = self.materialNameToNewReferenceIndexMap[section.name]
            sectionAnimPathPrefix = "m3_composite_materials[%s].sections[%s]." % (materialIndex, sectionIndex)
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Section, blenderObject=section, animPathPrefix=sectionAnimPathPrefix, rootObject=self.scene)
            shared.transferCompositeMaterialSection(transferer)
            m3Material.sections.append(m3Section)

        return m3Material

    def createTerrainMaterial(self, materialIndex, material):
        m3Material = self.createInstanceOf("TER_")
        materialAnimPathPrefix = "m3_terrain_materials[%s]." % materialIndex
        transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Material, blenderObject=material, animPathPrefix=materialAnimPathPrefix, rootObject=self.scene)
        shared.transferTerrainMaterial(transferer)
        m3Material.name = material.name
        self.createMaterialLayers(material, m3Material, materialAnimPathPrefix)
        return m3Material

    def createVolumeMaterial(self, materialIndex, material):
        m3Material = self.createInstanceOf("VOL_")
        materialAnimPathPrefix = "m3_volume_materials[%s]." % materialIndex
        transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Material, blenderObject=material, animPathPrefix=materialAnimPathPrefix, rootObject=self.scene)
        shared.transferVolumeMaterial(transferer)
        m3Material.name = material.name
        self.createMaterialLayers(material, m3Material, materialAnimPathPrefix)
        return m3Material

    def createCreepMaterial(self, materialIndex, material):
        m3Material = self.createInstanceOf("CREP")
        materialAnimPathPrefix = "m3_creep_materials[%s]." % materialIndex
        transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Material, blenderObject=material, animPathPrefix=materialAnimPathPrefix, rootObject=self.scene)
        shared.transferCreepMaterial(transferer)
        m3Material.name = material.name
        self.createMaterialLayers(material, m3Material, materialAnimPathPrefix)
        return m3Material

    def createVolumeNoiseMaterial(self, materialIndex, material):
        m3Material = self.createInstanceOf("VON_")
        materialAnimPathPrefix = "m3_volume_noise_materials[%s]." % materialIndex
        transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Material, blenderObject=material, animPathPrefix=materialAnimPathPrefix, rootObject=self.scene)
        shared.transferVolumeNoiseMaterial(transferer)
        m3Material.name = material.name
        self.createMaterialLayers(material, m3Material, materialAnimPathPrefix)
        # teh following unknown field needs to be 2 or the material is invisible:
        m3Material.noise1Layer[0].unknown3b61017a = 2
        m3Material.noise2Layer[0].unknown3b61017a = 2

        return m3Material

    def createSTBMaterial(self, materialIndex, material):
        m3Material = self.createInstanceOf("STBM")
        materialAnimPathPrefix = "m3_stb_materials[%s]." % materialIndex
        transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Material, blenderObject=material, animPathPrefix=materialAnimPathPrefix, rootObject=self.scene)
        shared.transfersplatTerrainBakeMaterial(transferer)
        m3Material.name = material.name
        self.createMaterialLayers(material, m3Material, materialAnimPathPrefix)
        return m3Material

    def createLensFlareMaterial(self, materialIndex, material):
        raise NotImplementedError()

    def createNullVector2AnimationReference(self, x, y, interpolationType=1):
        animRef = self.createInstanceOf("Vector2AnimationReference")
        animRef.header = self.createNullAnimHeader(interpolationType=interpolationType)
        animRef.initValue = self.createVector2(x, y)
        animRef.nullValue = self.createVector2(0.0, 0.0)
        return animRef

    def createNullVector3AnimationReference(self, x, y, z, initIsNullValue, interpolationType=1):
        animRef = self.createInstanceOf("Vector3AnimationReference")
        animRef.header = self.createNullAnimHeader(interpolationType=interpolationType)
        animRef.initValue = self.createVector3(x, y, z)
        if initIsNullValue:
            animRef.nullValue = self.createVector3(x, y, z)
        else:
            animRef.nullValue = self.createVector3(0.0, 0.0, 0.0)
        return animRef

    def createNullQuaternionAnimationReference(self, x=0.0, y=0.0, z=0.0, w=1.0):
        animRef = self.createInstanceOf("QuaternionAnimationReference")
        animRef.header = self.createNullAnimHeader(interpolationType=1)
        animRef.initValue = self.createQuaternion(x=x, y=y, z=z, w=w)
        animRef.nullValue = self.createQuaternion(x=x, y=y, z=z, w=w)
        return animRef

    def createNullInt16AnimationReference(self, value):
        animRef = self.createInstanceOf("Int16AnimationReference")
        animRef.header = self.createNullAnimHeader(interpolationType=1)
        animRef.initValue = value
        animRef.nullValue = 0
        return animRef

    def createNullFlagAnimationReference(self, value):
        animRef = self.createInstanceOf("FlagAnimationReference")
        animRef.header = self.createNullAnimHeader(interpolationType=1)
        animRef.initValue = value
        animRef.nullValue = 0
        return animRef

    def createNullUInt16AnimationReference(self, value):
        animRef = self.createInstanceOf("UInt16AnimationReference")
        animRef.header = self.createNullAnimHeader(interpolationType=0)
        animRef.initValue = value
        animRef.nullValue = 0
        return animRef

    def createNullUInt32AnimationReference(self, value, interpolationType=0):
        animRef = self.createInstanceOf("UInt32AnimationReference")
        animRef.header = self.createNullAnimHeader(interpolationType=interpolationType)
        animRef.initValue = value
        animRef.nullValue = 0
        return animRef

    def createNullFloatAnimationReference(self, initValue, nullValue=None, interpolationType=1):
        if nullValue is None:
            nullValue = initValue
        animRef = self.createInstanceOf("FloatAnimationReference")
        animRef.header = self.createNullAnimHeader(interpolationType=interpolationType)
        animRef.initValue = initValue
        animRef.nullValue = 0.0
        return animRef

    def createNullAnimHeader(self, interpolationType, animId=None):
        animRefHeader = self.createInstanceOf("AnimationReferenceHeader")
        animRefHeader.interpolationType = interpolationType
        animRefHeader.animFlags = 0
        if animId is None:
            animRefHeader.animId = self.createUniqueAnimId()
        else:
            animRefHeader.animId = animId
        return animRefHeader

    def createMaterialReference(self, materialIndex, materialType):
        materialReference = self.createInstanceOf("MATM")
        materialReference.materialType = materialType
        materialReference.materialIndex = materialIndex
        return materialReference

    def createEmptyDivision(self):
        division = self.createInstanceOf("DIV_")
        division.faces = []
        division.regions = []
        division.objects = []
        division.msec = [self.createEmptyMSec()]
        return division

    def createEmptyMSec(self, minX=0.0, minY=0.0, minZ=0.0, maxX=0.0, maxY=0.0, maxZ=0.0, radius=0.0):
        msec = self.createInstanceOf("MSEC")
        msec.boundingsAnimation = self.createDummyBoundingsAnimation(minX, minY, minZ, maxX, maxY, maxZ, radius)
        return msec

    def createDummyBoundingsAnimation(self, minX=0.0, minY=0.0, minZ=0.0, maxX=0.0, maxY=0.0, maxZ=0.0, radius=0.0):
        boundingsAnimRef = self.createInstanceOf("BNDSV0AnimationReference")
        animHeader = self.createInstanceOf("AnimationReferenceHeader")
        animHeader.interpolationType = 0
        animHeader.animFlags = 0x0
        animHeader.animId = self.boundingAnimId  # boudings seem to have always this id
        boundingsAnimRef.header = animHeader
        boundingsAnimRef.initValue = self.createBoundings(minX, minY, minZ, maxX, maxY, maxZ, radius)
        boundingsAnimRef.nullValue = self.createBoundings(minX, minY, minZ, maxX, maxY, maxZ, radius)
        return boundingsAnimRef

    def createBoundings(self, minX=0.0, minY=0.0, minZ=0.0, maxX=0.0, maxY=0.0, maxZ=0.0, radius=0.0):
        boundings = self.createInstanceOf("BNDS")
        boundings.minBorder = self.createVector3(minX, minY, minZ)
        boundings.maxBorder = self.createVector3(maxX, maxY, maxZ)
        boundings.radius = radius
        return boundings

    def createAlmostEmptyBoundingsWithRadius(self, r):
        boundings = self.createInstanceOf("BNDS")
        boundings.minBorder = self.createVector3(0.0, 0.0, 0.0)
        epsilon = 9.5367431640625e-07
        boundings.maxBorder = self.createVector3(epsilon, epsilon, epsilon)
        boundings.radius = float(r)
        return boundings

    def createVector4(self, x, y, z, w):
        v = self.createInstanceOf("VEC4")
        v.x = x
        v.y = y
        v.z = z
        v.w = w
        return v

    def createQuaternion(self, x, y, z, w):
        q = self.createInstanceOf("QUAT")
        q.x = x
        q.y = y
        q.z = z
        q.w = w
        return q

    def createColor(self, r, g, b, a):
        color = self.createInstanceOf("COL")
        color.red = self.toM3ColorComponent(r)
        color.green = self.toM3ColorComponent(g)
        color.blue = self.toM3ColorComponent(b)
        color.alpha = self.toM3ColorComponent(a)
        return color

    def createVector3(self, x, y, z):
        v = self.createInstanceOf("VEC3")
        v.x = x
        v.y = y
        v.z = z
        return v

    def createVector2(self, x, y):
        v = self.createInstanceOf("VEC2")
        v.x = x
        v.y = y
        return v

    def createVector3FromBlenderVector(self, blenderVector):
        return self.createVector3(blenderVector.x, blenderVector.y, blenderVector.z)

    def createVector3sFromBlenderVectors(self, blenderVectors):
        m3Vectors = []
        for blenderVector in blenderVectors:
            m3Vectors.append(self.createVector3FromBlenderVector(blenderVector))
        return m3Vectors

    def createVector4FromBlenderVector(self, blenderVector):
        return self.createVector4(blenderVector[0], blenderVector[1], blenderVector[2], blenderVector[3])

    def createQuaternionFromBlenderQuaternion(self, q):
        return self.createQuaternion(x=q.x, y=q.y, z=q.z, w=q.w)

    def createQuaternionsFromBlenderQuaternions(self, blenderQuaternions):
        m3Quaternions = []
        for blenderQuaternion in blenderQuaternions:
            m3Quaternions.append(self.createQuaternionFromBlenderQuaternion(blenderQuaternion))
        return m3Quaternions

    def createIdentityMatrix(self):
        matrix = self.createInstanceOf("Matrix44")
        matrix.x = self.createVector4(1.0, 0.0, 0.0, 0.0)
        matrix.y = self.createVector4(0.0, 1.0, 0.0, 0.0)
        matrix.z = self.createVector4(0.0, 0.0, 1.0, 0.0)
        matrix.w = self.createVector4(0.0, 0.0, 0.0, 1.0)
        return matrix

    def determineAnimationActionTuplesFor(self, ob):
        """ returns (animation, action) tuples for all animations of the given object"""

        animationData = ob.animation_data
        animationActionTuples = []

        for animationIndex in self.animationIndicesToExport:
            animation = self.scene.m3_animations[animationIndex]
            action = None
            if animationData is not None:
                action = bpy.data.actions[ob.name + animation.name] if ob.name + animation.name in bpy.data.actions else None
            animationActionTuples.append((animation, action))

        return animationActionTuples

    def allFramesToMSValues(self, frames):
        timeValues = []
        for frame in frames:
            timeInMS = self.frameToMS(frame)
            timeValues.append(timeInMS)
        return timeValues

    def getNoneOrValuesFor(self, action, animPath, curveArrayIndex, frames):
        """ returns None if action == None or the action does not contain the specified animation path"""
        values = []
        if action is None:
            return None
        curve = self.findFCurveWithPathAndIndex(action, animPath, curveArrayIndex)
        if curve is None:
            return None
        for frame in frames:
            values.append(curve.evaluate(frame))
        return values

    def getFramesFor(self, action, animPath, curveArrayIndex):
        """ action can be None in which case an empty frames list is returned"""
        frames = []
        if action is None:
            return frames
        curve = self.findFCurveWithPathAndIndex(action, animPath, curveArrayIndex)
        if curve is None:
            return frames
        lastInterpolation = "LINEAR"
        for keyframePoint in curve.keyframe_points:
            frame = int(round(keyframePoint.co.x))
            if lastInterpolation != "LINEAR":
                for f in range(frame):
                    frames.append(f)
            frames.append(frame)
        return frames

    def findFCurveWithPathAndIndex(self, action, animPath, curveArrayIndex):
        for curve in action.fcurves:
            if (curve.data_path == animPath) and (curve.array_index == curveArrayIndex):
                return curve
        return None

    def fCurveExistsForPath(self, action, animPath):
        for curve in action.fcurves:
            if (curve.data_path == animPath):
                return True
        return False

    def getDefaultValue(self, rootObject, path, index, currentValue):
        if not hasattr(self, "objectToDefaultValuesMap"):
            self.objectToDefaultValuesMap = {}
        objectId = id(rootObject)
        animatedPropertyToDefaultValueMap = self.objectToDefaultValuesMap.get(objectId)

        if animatedPropertyToDefaultValueMap is None:
            animatedPropertyToDefaultValueMap = {}
            if rootObject.animation_data is not None:
                animatedProperties = set()
                currentAction = rootObject.animation_data.action
                if currentAction is not None:
                    for curve in currentAction.fcurves:
                        animatedProperties.add((curve.data_path, curve.array_index))

                defaultAction = shared.getOrCreateDefaultActionFor(rootObject)
                if len(animatedProperties) > 0:
                    for curve in defaultAction.fcurves:
                        prop = (curve.data_path, curve.array_index)
                        if prop in animatedProperties:
                            animatedPropertyToDefaultValueMap[prop] = curve.evaluate(0)

            self.objectToDefaultValuesMap[objectId] = animatedPropertyToDefaultValueMap
        defaultValue = animatedPropertyToDefaultValueMap.get((path, index))
        if defaultValue is not None:
            return defaultValue
        else:
            return currentValue


class BlenderToM3DataTransferer:
    def __init__(self, exporter, m3Object, blenderObject, animPathPrefix, rootObject):
        self.exporter = exporter
        self.m3Object = m3Object
        self.blenderObject = blenderObject
        self.animPathPrefix = animPathPrefix
        self.objectIdForAnimId = shared.animObjectIdScene
        self.animationActionTuples = self.exporter.determineAnimationActionTuplesFor(rootObject)
        self.rootObject = rootObject
        self.m3Version = m3Object.structureDescription.structureVersion

    def transferAnimatableColor(self, fieldName):
        animPath = self.animPathPrefix + fieldName
        animId = self.exporter.getAnimIdFor(self.objectIdForAnimId, animPath)
        animRef = self.exporter.createInstanceOf("ColorAnimationReference")
        animRef.header = self.exporter.createNullAnimHeader(animId=animId, interpolationType=1)
        currentColor = getattr(self.blenderObject, fieldName)
        defaultColor = mathutils.Vector((0, 0, 0, 1.0))
        for i in range(len(currentColor)):
            defaultColor[i] = self.exporter.getDefaultValue(self.rootObject, animPath, i, currentColor[i])
        m3DefaultColor = self.exporter.toM3Color(defaultColor)
        animRef.initValue = m3DefaultColor
        animRef.nullValue = self.exporter.createColor(0, 0, 0, 0)
        setattr(self.m3Object, fieldName, animRef)

        for animation, action in self.animationActionTuples:
            frames = set()
            for i in range(4):
                frames.update(self.exporter.getFramesFor(action, animPath, i))
            frames = list(frames)
            frames.sort()
            timeValuesInMS = self.exporter.allFramesToMSValues(frames)
            redValues = self.exporter.getNoneOrValuesFor(action, animPath, 0, frames)
            greenValues = self.exporter.getNoneOrValuesFor(action, animPath, 1, frames)
            blueValues = self.exporter.getNoneOrValuesFor(action, animPath, 2, frames)
            alphaValues = self.exporter.getNoneOrValuesFor(action, animPath, 3, frames)
            if (redValues is not None) or (greenValues is not None) or (blueValues is not None) or (alphaValues is not None):
                if redValues is None:
                    redValues = len(timeValuesInMS) * [m3DefaultColor.red]
                if greenValues is None:
                    greenValues = len(timeValuesInMS) * [m3DefaultColor.green]
                if blueValues is None:
                    blueValues = len(timeValuesInMS) * [m3DefaultColor.blue]
                if alphaValues is None:
                    alphaValues = len(timeValuesInMS) * [m3DefaultColor.alpha]
                colors = []
                for (r, g, b, a) in zip(redValues, greenValues, blueValues, alphaValues):
                    color = self.exporter.createColor(r=r, g=g, b=b, a=a)
                    colors.append(color)

                m3AnimBlock = self.exporter.createInstanceOf("SDCC")
                m3AnimBlock.frames = timeValuesInMS
                m3AnimBlock.flags = 0
                m3AnimBlock.fend = self.exporter.frameToMS(animation.exlusiveEndFrame)
                m3AnimBlock.keys = colors

                animIdToAnimDataMap = self.exporter.nameToAnimIdToAnimDataMap[animation.name]
                animIdToAnimDataMap[animId] = m3AnimBlock
                animRef.header.animFlags = shared.animFlagsForAnimatedProperty
        # TODO Optimization: Remove keyframes that can be calculated by interpolation

    def transferAnimatableSingleFloatOrInt(self, fieldName, animRefClass, animRefFlags, animDataClass, convertMethod):
        animPath = self.animPathPrefix + fieldName
        animId = self.exporter.getAnimIdFor(self.objectIdForAnimId, animPath)
        animRef = self.exporter.createInstanceOf(animRefClass)
        animRef.header = self.exporter.createNullAnimHeader(animId=animId, interpolationType=1)
        currentValue = getattr(self.blenderObject, fieldName)
        defaultValue = convertMethod(self.exporter.getDefaultValue(self.rootObject, animPath, 0, currentValue))

        animRef.initValue = defaultValue
        animRef.nullValue = type(defaultValue)(0)
        for animation, action in self.animationActionTuples:
            frames = list(set(self.exporter.getFramesFor(action, animPath, 0)))
            frames.sort()
            timeValuesInMS = self.exporter.allFramesToMSValues(frames)
            values = self.exporter.getNoneOrValuesFor(action, animPath, 0, frames)
            if values is not None:
                if (type(defaultValue) == float):
                    timeValuesInMS, values = shared.simplifyFloatAnimationWithInterpolation(timeValuesInMS, values)
                convertedValues = []
                for value in values:
                    convertedValues.append(convertMethod(value))
                m3AnimBlock = self.exporter.createInstanceOf(animDataClass)
                m3AnimBlock.frames = timeValuesInMS
                m3AnimBlock.flags = 0
                m3AnimBlock.fend = self.exporter.frameToMS(animation.exlusiveEndFrame)
                m3AnimBlock.keys = convertedValues

                animIdToAnimDataMap = self.exporter.nameToAnimIdToAnimDataMap[animation.name]
                animIdToAnimDataMap[animId] = m3AnimBlock
                animRef.header.animFlags = shared.animFlagsForAnimatedProperty
        # TODO Optimization: Remove keyframes that can be calculated by interpolation
        setattr(self.m3Object, fieldName, animRef)

    def transferAnimatableFloat(self, fieldName):
        def identity(value):
            return value
        self.transferAnimatableSingleFloatOrInt(fieldName, animRefClass="FloatAnimationReference", animRefFlags=1, animDataClass="SDR3", convertMethod=identity)

    def transferAnimatableInt16(self, fieldName):
        def toInt16Value(value):
            return min((1 << 15) - 1, max(-(1 << 15), round(value)))
        self.transferAnimatableSingleFloatOrInt(fieldName, animRefClass="Int16AnimationReference", animRefFlags=0, animDataClass="SDS6", convertMethod=toInt16Value)

    def transferAnimatableUInt16(self, fieldName):
        def toUInt16Value(value):
            return min((1 << 16) - 1, max(0, round(value)))
        self.transferAnimatableSingleFloatOrInt(fieldName, animRefClass="UInt16AnimationReference", animRefFlags=0, animDataClass="SDU6", convertMethod=toUInt16Value)

    def transferAnimatableUInt32(self, fieldName):
        def toUInt32Value(value):
            return min((1 << 32) - 1, max(0, round(value)))
        self.transferAnimatableSingleFloatOrInt(fieldName, animRefClass="UInt32AnimationReference", animRefFlags=0, animDataClass="SDU6", convertMethod=toUInt32Value)

    def transferAnimatableBooleanBasedOnSDFG(self, fieldName):
        def convertTo1Or0(value):
            if not isinstance(value, bool):
                booleanValue = value
            else:
                booleanValue = (value >= 0.5)
            return 1 if booleanValue else 0
        self.transferAnimatableSingleFloatOrInt(fieldName, animRefClass="UInt32AnimationReference", animRefFlags=0, animDataClass="SDFG", convertMethod=convertTo1Or0)

    def transferAnimatableBooleanBasedOnSDU3(self, fieldName):
        def convertTo1Or0(value):
            if not isinstance(value, bool):
                booleanValue = value
            else:
                booleanValue = (value >= 0.5)
            return 1 if booleanValue else 0
        self.transferAnimatableSingleFloatOrInt(fieldName, animRefClass="UInt32AnimationReference", animRefFlags=0, animDataClass="SDU3", convertMethod=convertTo1Or0)

    def transferAnimatableVector3(self, fieldName, sinceVersion=None):
        if (sinceVersion is not None) and (self.m3Version < sinceVersion):
            return
        animPath = self.animPathPrefix + fieldName
        animId = self.exporter.getAnimIdFor(self.objectIdForAnimId, animPath)
        animRef = self.exporter.createInstanceOf("Vector3AnimationReference")
        animRef.header = self.exporter.createNullAnimHeader(animId=animId, interpolationType=1)
        currentBVector = getattr(self.blenderObject, fieldName)

        defaultValueX = self.exporter.getDefaultValue(self.rootObject, animPath, 0, currentBVector[0])
        defaultValueY = self.exporter.getDefaultValue(self.rootObject, animPath, 1, currentBVector[1])
        defaultValueZ = self.exporter.getDefaultValue(self.rootObject, animPath, 2, currentBVector[2])
        animRef.initValue = self.exporter.createVector3(defaultValueX, defaultValueY, defaultValueZ)
        animRef.nullValue = self.exporter.createVector3(0.0, 0.0, 0.0)
        setattr(self.m3Object, fieldName, animRef)

        for animation, action in self.animationActionTuples:
            frames = set()
            for i in range(3):
                frames.update(self.exporter.getFramesFor(action, animPath, i))
            frames = list(frames)
            frames.sort()
            timeValuesInMS = self.exporter.allFramesToMSValues(frames)
            xValues = self.exporter.getNoneOrValuesFor(action, animPath, 0, frames)
            yValues = self.exporter.getNoneOrValuesFor(action, animPath, 1, frames)
            zValues = self.exporter.getNoneOrValuesFor(action, animPath, 2, frames)
            if (xValues is not None) or (yValues is not None) or (zValues is not None):
                if xValues is None:
                    xValues = len(timeValuesInMS) * [currentBVector.x]  # TODO should be defaultValueX
                if yValues is None:
                    yValues = len(timeValuesInMS) * [currentBVector.y]
                if zValues is None:
                    zValues = len(timeValuesInMS) * [currentBVector.z]
                vectors = []
                for (x, y, z) in zip(xValues, yValues, zValues):
                    vec = self.exporter.createVector3(x, y, z)
                    vectors.append(vec)

                m3AnimBlock = self.exporter.createInstanceOf("SD3V")
                m3AnimBlock.frames = timeValuesInMS
                m3AnimBlock.flags = 0
                m3AnimBlock.fend = self.exporter.frameToMS(animation.exlusiveEndFrame)
                m3AnimBlock.keys = vectors

                animIdToAnimDataMap = self.exporter.nameToAnimIdToAnimDataMap[animation.name]
                animIdToAnimDataMap[animId] = m3AnimBlock
                animRef.header.animFlags = shared.animFlagsForAnimatedProperty
        # TODO Optimization: Remove keyframes that can be calculated by interpolation

    def transferAnimatableBoundings(self):
        animPathMinBorder = self.animPathPrefix + "minBorder"
        animPathMaxBorder = self.animPathPrefix + "maxBorder"
        animPathRadius = self.animPathPrefix + "radius"

        # assume animation ref does already exist:
        animRef = self.m3Object
        animId = animRef.header.animId
        boundings = self.blenderObject

        defaultMinBorder = mathutils.Vector((0, 0, 0))
        for i in range(3):
            defaultMinBorder[i] = self.exporter.getDefaultValue(self.rootObject, animPathMinBorder, i, boundings.minBorder[i])
        defaultMaxBorder = mathutils.Vector((0, 0, 0))
        for i in range(3):
            defaultMaxBorder[i] = self.exporter.getDefaultValue(self.rootObject, animPathMaxBorder, i, boundings.maxBorder[i])
        defaultRadius = self.exporter.getDefaultValue(self.rootObject, animPathRadius, 0, boundings.radius)
        m3DefaultBoundings = self.exporter.createInstanceOf("BNDS")
        m3DefaultBoundings.minBorder = self.exporter.createVector3FromBlenderVector(defaultMinBorder)
        m3DefaultBoundings.maxBorder = self.exporter.createVector3FromBlenderVector(defaultMaxBorder)
        m3DefaultBoundings.radius = defaultRadius
        animRef.initValue = m3DefaultBoundings
        animRef.nullValue = self.exporter.createBoundings()
        for animation, action in self.animationActionTuples:
            frames = set()
            for i in range(3):
                frames.update(self.exporter.getFramesFor(action, animPathMinBorder, i))
            for i in range(3):
                frames.update(self.exporter.getFramesFor(action, animPathMaxBorder, i))
            frames.update(self.exporter.getFramesFor(action, animPathRadius, i))
            frames = list(frames)
            frames.sort()
            timeValuesInMS = self.exporter.allFramesToMSValues(frames)

            minBorderXValues = self.exporter.getNoneOrValuesFor(action, animPathMinBorder, 0, frames)
            minBorderYValues = self.exporter.getNoneOrValuesFor(action, animPathMinBorder, 1, frames)
            minBorderZValues = self.exporter.getNoneOrValuesFor(action, animPathMinBorder, 2, frames)
            maxBorderXValues = self.exporter.getNoneOrValuesFor(action, animPathMaxBorder, 0, frames)
            maxBorderYValues = self.exporter.getNoneOrValuesFor(action, animPathMaxBorder, 1, frames)
            maxBorderZValues = self.exporter.getNoneOrValuesFor(action, animPathMaxBorder, 2, frames)
            radiusValues = self.exporter.getNoneOrValuesFor(action, animPathRadius, 0, frames)

            isAnimated = False
            isAnimated |= (minBorderXValues is not None)
            isAnimated |= (minBorderYValues is not None)
            isAnimated |= (minBorderZValues is not None)
            isAnimated |= (maxBorderXValues is not None)
            isAnimated |= (maxBorderYValues is not None)
            isAnimated |= (maxBorderZValues is not None)
            isAnimated |= (radiusValues is not None)
            if isAnimated:
                if minBorderXValues is None:
                    minBorderXValues = len(timeValuesInMS) * [defaultMinBorder.x]
                if minBorderYValues is None:
                    minBorderYValues = len(timeValuesInMS) * [defaultMinBorder.y]
                if minBorderZValues is None:
                    minBorderZValues = len(timeValuesInMS) * [defaultMinBorder.z]
                if maxBorderXValues is None:
                    maxBorderXValues = len(timeValuesInMS) * [defaultMaxBorder.x]
                if maxBorderYValues is None:
                    maxBorderYValues = len(timeValuesInMS) * [defaultMaxBorder.y]
                if maxBorderZValues is None:
                    maxBorderZValues = len(timeValuesInMS) * [defaultMaxBorder.z]
                if radiusValues is None:
                    radiusValues = len(timeValuesInMS) * [defaultRadius]
                boundingsList = []
                for (minX, minY, minZ, maxX, maxY, maxZ, radius) in zip(minBorderXValues, minBorderYValues, minBorderZValues, maxBorderXValues, maxBorderYValues, maxBorderZValues, radiusValues):
                    b = self.exporter.createInstanceOf("BNDS")
                    b.minBorder = self.exporter.createVector3(minX, minY, minZ)
                    b.maxBorder = self.exporter.createVector3(maxX, maxY, maxZ)
                    b.radius = radius
                    boundingsList.append(b)

                m3AnimBlock = self.exporter.createInstanceOf("SDMB")
                m3AnimBlock.frames = timeValuesInMS
                m3AnimBlock.flags = 0
                m3AnimBlock.fend = self.exporter.frameToMS(animation.exlusiveEndFrame)
                m3AnimBlock.keys = boundingsList

                animIdToAnimDataMap = self.exporter.nameToAnimIdToAnimDataMap[animation.name]
                animIdToAnimDataMap[animId] = m3AnimBlock
                animRef.header.animFlags = shared.animFlagsForAnimatedProperty

    def transferAnimatableVector2(self, fieldName):
        animPath = self.animPathPrefix + fieldName
        animId = self.exporter.getAnimIdFor(self.objectIdForAnimId, animPath)
        animRef = self.exporter.createInstanceOf("Vector2AnimationReference")
        animRef.header = self.exporter.createNullAnimHeader(animId=animId, interpolationType=1)
        currentBVector = getattr(self.blenderObject, fieldName)

        defaultValueX = self.exporter.getDefaultValue(self.rootObject, animPath, 0, currentBVector[0])
        defaultValueY = self.exporter.getDefaultValue(self.rootObject, animPath, 1, currentBVector[1])
        animRef.initValue = self.exporter.createVector2(defaultValueX, defaultValueY)
        animRef.nullValue = self.exporter.createVector2(0.0, 0.0)
        setattr(self.m3Object, fieldName, animRef)

        for animation, action in self.animationActionTuples:
            frames = set()
            for i in range(2):
                frames.update(self.exporter.getFramesFor(action, animPath, i))
            frames = list(frames)
            frames.sort()
            timeValuesInMS = self.exporter.allFramesToMSValues(frames)
            xValues = self.exporter.getNoneOrValuesFor(action, animPath, 0, frames)
            yValues = self.exporter.getNoneOrValuesFor(action, animPath, 1, frames)
            if (xValues is not None) or (yValues is not None):
                if xValues is None:
                    xValues = len(timeValuesInMS) * [currentBVector.x]
                if yValues is None:
                    yValues = len(timeValuesInMS) * [currentBVector.y]

                vectors = []
                for (x, y) in zip(xValues, yValues):
                    vec = self.exporter.createVector2(x, y)
                    vectors.append(vec)

                m3AnimBlock = self.exporter.createInstanceOf("SD2V")
                m3AnimBlock.frames = timeValuesInMS
                m3AnimBlock.flags = 0
                m3AnimBlock.fend = self.exporter.frameToMS(animation.exlusiveEndFrame)
                m3AnimBlock.keys = vectors

                animIdToAnimDataMap = self.exporter.nameToAnimIdToAnimDataMap[animation.name]
                animIdToAnimDataMap[animId] = m3AnimBlock
                animRef.header.animFlags = shared.animFlagsForAnimatedProperty
        # TODO Optimization: Remove keyframes that can be calculated by interpolation

    def transferInt(self, fieldName, sinceVersion=None):
        if (sinceVersion is not None) and (self.m3Version < sinceVersion):
            return
        value = getattr(self.blenderObject, fieldName)
        setattr(self.m3Object, fieldName, value)

    def transferBoolean(self, fieldName, sinceVersion=None, tillVersion=None):
        if (sinceVersion is not None and self.m3Version < sinceVersion) or (tillVersion is not None and self.m3Version > tillVersion):
            return
        booleanValue = getattr(self.blenderObject, fieldName)
        if booleanValue:
            intValue = 1
        else:
            intValue = 0
        setattr(self.m3Object, fieldName, intValue)

    def transferBit(self, m3FieldName, bitName, sinceVersion=None, tillVersion=None):
        if (sinceVersion is not None and self.m3Version < sinceVersion) or (tillVersion is not None and self.m3Version > tillVersion):
            return
        booleanValue = getattr(self.blenderObject, bitName)
        self.m3Object.setNamedBit(m3FieldName, bitName, booleanValue)

    def transferBitEnum(self, m3FieldName, bitName, sinceVersion=None):
        if (sinceVersion is not None) and (self.m3Version < sinceVersion):
            return
        value = getattr(self.blenderObject, bitName)
        self.m3Object.setNamedBit(m3FieldName, bitName, int(value))

    def transferMultipleBits(self, m3FieldName, bNameList=None):
        field = self.m3Object.structureDescription.nameToFieldMap[m3FieldName]
        if bNameList is None:
            bNameList = [x for x in field.bitMaskMap]
        for bitName in bNameList:
            self.transferBit(m3FieldName, bitName)

    def transfer16Bits(self, fieldName):
        vector = getattr(self.blenderObject, fieldName)
        integerValue = 0
        for bitIndex in range(0, 16):
            if vector[bitIndex]:
                mask = 1 << bitIndex
                integerValue |= mask
        setattr(self.m3Object, fieldName, integerValue)

    def transfer32Bits(self, fieldName):
        vector = getattr(self.blenderObject, fieldName)
        integerValue = 0
        for bitIndex in range(0, 32):
            if vector[bitIndex]:
                mask = 1 << bitIndex
                integerValue |= mask
        setattr(self.m3Object, fieldName, integerValue)

    def transferFloat(self, fieldName, sinceVersion=None, tillVersion=None):
        if (tillVersion is not None) and (self.m3Version > tillVersion):
            return
        if (sinceVersion is not None) and (self.m3Version < sinceVersion):
            return
        value = getattr(self.blenderObject, fieldName)
        setattr(self.m3Object, fieldName, value)

    def transferString(self, fieldName):
        value = getattr(self.blenderObject, fieldName)
        setattr(self.m3Object, fieldName, value)

    def transferEnum(self, fieldName, sinceVersion=None):
        if (sinceVersion is not None) and (self.m3Version < sinceVersion):
            return
        value = getattr(self.blenderObject, fieldName)
        setattr(self.m3Object, fieldName, int(value))


def export(scene: bpy.types.Scene, operator: bpy.types.Operator, filename):
    exporter = Exporter(scene, operator)

    tmp_anim_index = scene.m3_animation_index
    tmp_anim_frame = scene.frame_current

    try:
        start_time = time.time()
        exporter.export(filename)
        end_time = time.time()
        print(-(start_time - end_time))
        return {'FINISHED'}
    except ExportError as e:
        mlog.exception('failed to export')
        operator.report({'ERROR'}, f'M3Export failed: {str(e)}')
    except:
        mlog.exception('failed to export')
        raise
    finally:
        # restore animation selection
        if scene.m3_animation_index != tmp_anim_index:
            scene.m3_animation_index = tmp_anim_index
        scene.frame_current = tmp_anim_frame
    return {'CANCELLED'}
