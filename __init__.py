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

bl_info = {
    "name": "m3addon for M3 format: used by Blizzard's StarCraft 2 and Heroes of the Storm",
    "author": "Florian Köberle, netherh, chaos2night, Talv, Solstice245",
    "version": (0, 5, 1),
    "blender": (2, 80, 0),
    "location": "Properties Editor -> Scene -> M3 Panels",
    "description": "Allows to export and import models in M3 format.",
    "category": "Import-Export",
    "doc_url": "https://github.com/SC2Mapster/m3addon/blob/master/README.md",
    "tracker_url": "https://github.com/SC2Mapster/m3addon/issues"
}

# force reload of imported modules on second load of __init__.py
# that is when `Reload Scripts` action is used in the blender interface
if "bpy" in locals() and "mlog" in locals():
    import imp
    localModules = [
        ["shared"],
        ["cm", "base"],
        ["cm", "material"],
        ["cm", "projection"],
        ["cm"],
        ["im", "material"],
        ["im"],
        ["ui", "base"],
        ["ui", "projection"],
        ["ui"],
        ["m3"],
        ["m3import"],
        ["m3export"],
    ]
    mlog.debug("Reloading modules....")
    for plist in localModules:
        try:
            # mlog.debug("Reloading \"%s\"" % ".".join(plist))
            submod = dict(locals())[plist.pop(0)]
            while submod:
                mlog.debug("Reloading \"%s\"" % submod)
                imp.reload(submod)
                if not len(plist):
                    break
                currName = plist.pop(0)
                submod = submod.__dict__[currName]
        except KeyError as e:
            mlog.debug("Failed to reload %s" % e)
    mlog.debug("Reloaded modules!")

import bpy
import bpy.types as bt
import math
import bmesh
from .common import mlog
from . import shared
from .shared import selectBone, removeBone, selectOrCreateBone, selectBoneIfItExists
from . import cm
from . import ui


def boneNameSet():
    boneNames = set()
    for armature in bpy.data.armatures:
        for bone in armature.bones:
            boneNames.add(bone.name)
        for bone in armature.edit_bones:
            boneNames.add(bone.name)
    return boneNames


def availableBones(self, context):
    sortedBoneNames = []
    sortedBoneNames.extend(boneNameSet())
    sortedBoneNames.sort()
    list = [("", "None", "Not assigned to a bone")]

    for boneName in sortedBoneNames:
        list.append((boneName, boneName, boneName))
    return list


def availableMaterials(self, context):
    list = [("", "None", "No Material")]
    for material in context.scene.m3_material_references:
        list.append((material.name, material.name, material.name))
    return list


def swapActionSceneM3Keyframes(prefix, old, shift):
    for action in bpy.data.actions:
        if "Scene" not in action.name:
            continue

        fcurves = []
        fcurvesShift = []

        for fcurve in action.fcurves:
            if prefix in fcurve.data_path:
                pathId = "{pre}[{ii}]".format(pre=prefix, ii=old)
                pathIdShift = "{pre}[{ii}]".format(pre=prefix, ii=old + shift)

                if pathId in fcurve.data_path:
                    fcurve.data_path = fcurve.data_path.replace(pathId, prefix + "[temp]")
                    fcurves.append(fcurve)

                if pathIdShift in fcurve.data_path:
                    fcurve.data_path = fcurve.data_path.replace(pathIdShift, prefix + "[tempShift]")
                    fcurvesShift.append(fcurve)

        for fcurve in fcurves:
            fcurve.data_path = fcurve.data_path.replace(prefix + "[temp]", pathIdShift)

        for fcurve in fcurvesShift:
            fcurve.data_path = fcurve.data_path.replace(prefix + "[tempShift]", pathId)


def updateBoneShapesOfParticleSystemCopies(scene, particleSystem):
    for copy in particleSystem.copies:
        boneName = copy.boneName
        bone, armatureObject = shared.findBoneWithArmatureObject(scene, boneName)
        if bone is not None:
            poseBone = armatureObject.pose.bones[boneName]
            shared.updateBoneShapeOfParticleSystem(particleSystem, bone, poseBone)


def handleAttachmentPointNameOrTypeChange(self, context):
    if not self.bl_update:
        return

    attachmentPoint = self
    scene = context.scene

    currentBoneName = attachmentPoint.boneName
    calculatedBoneName = shared.boneNameForAttachmentPoint(attachmentPoint)

    if currentBoneName != calculatedBoneName:
        bone, armatureObject = shared.findBoneWithArmatureObject(scene, currentBoneName)
        if bone is not None:
            bone.name = calculatedBoneName
            attachmentPoint.boneName = bone.name
        else:
            attachmentPoint.boneName = calculatedBoneName

    selectOrCreateBoneForAttachmentPoint(scene, attachmentPoint)


def handleGeometricShapeTypeOrBoneNameUpdate(self, context):
    shapeObject = self
    scene = context.scene

    typeName = "Unknown"
    for typeId, name, description in geometricShapeTypeList:
        if typeId == shapeObject.shape:
            typeName = name

    shapeObject.name = "{name} ({type})".format(name=shapeObject.boneName, type=typeName)

    selectOrCreateBoneForShapeObject(scene, shapeObject)


def handleParticleSystemNameChange(self, context):
    if not self.bl_update:
        return

    particleSystem = self
    scene = context.scene

    currentBoneName = particleSystem.boneName
    calculatedBoneName = shared.boneNameForParticleSystem(particleSystem)

    if currentBoneName != calculatedBoneName:
        bone, armatureObject = shared.findBoneWithArmatureObject(scene, currentBoneName)
        if bone is not None:
            bone.name = calculatedBoneName
            particleSystem.boneName = bone.name
        else:
            particleSystem.boneName = calculatedBoneName

    selectOrCreateBoneForParticleSystem(scene, particleSystem)
    updateBoneShapesOfParticleSystemCopies(scene, particleSystem)


def handleParticleSystemCopyNameChange(self, context):
    scene = context.scene
    particleSystemCopy = self

    currentBoneName = particleSystemCopy.boneName
    calculatedBoneName = shared.boneNameForParticleSystem(particleSystemCopy)

    if currentBoneName != calculatedBoneName:
        bone, armatureObject = shared.findBoneWithArmatureObject(scene, currentBoneName)
        if bone is not None:
            bone.name = calculatedBoneName
            particleSystemCopy.boneName = bone.name
        else:
            particleSystemCopy.boneName = calculatedBoneName


def handleRibbonNameChange(self, context):
    if not self.bl_update:
        return

    ribbon = self
    scene = context.scene

    currentBoneName = ribbon.boneName
    calculatedBoneName = shared.boneNameForRibbon(ribbon)

    if currentBoneName != calculatedBoneName:
        bone, armatureObject = shared.findBoneWithArmatureObject(scene, currentBoneName)
        if bone is not None:
            bone.name = calculatedBoneName
            ribbon.boneName = bone.name
        else:
            ribbon.boneName = calculatedBoneName

    selectOrCreateBoneForRibbon(scene, ribbon)
    # TODO for sub ribbons:
    # updateBoneShapesOfSubRibbons(scene, ribbon)


def handleParticleSystemAreaSizeChange(self, context):
    if not self.bl_update:
        return

    particleSystem = self
    scene = context.scene
    selectOrCreateBoneForParticleSystem(scene, particleSystem)
    updateBoneShapesOfParticleSystemCopies(scene, particleSystem)


def handleForceNameOrTypeChange(self, context):
    if not self.bl_update:
        return

    scene = context.scene
    force = self

    currentBoneName = force.boneName
    calculatedBoneName = shared.boneNameForForce(force)

    if currentBoneName != calculatedBoneName:
        bone, armatureObject = shared.findBoneWithArmatureObject(scene, currentBoneName)
        if bone is not None:
            bone.name = calculatedBoneName
            force.boneName = bone.name
        else:
            force.boneName = calculatedBoneName

    selectOrCreateBoneForForce(scene, force)


def handleForceShapeUpdate(self, context):
    if not self.bl_update:
        return

    scene = context.scene
    force = self
    selectOrCreateBoneForForce(scene, force)


def handleLightNameOrTypeChange(self, context):
    if not self.bl_update:
        return

    scene = context.scene
    light = self

    currentBoneName = light.boneName
    calculatedBoneName = shared.boneNameForLight(light)

    if currentBoneName != calculatedBoneName:
        bone, armatureObject = shared.findBoneWithArmatureObject(scene, currentBoneName)
        if bone is not None:
            bone.name = calculatedBoneName
            light.boneName = bone.name
        else:
            light.boneName = calculatedBoneName
    selectOrCreateBoneForLight(scene, light)


def handleLightSizeChange(self, context):
    if not self.bl_update:
        return

    scene = context.scene
    light = self
    selectOrCreateBoneForLight(scene, light)


def handleWarpRadiusChange(self, context):
    if not self.bl_update:
        return

    scene = context.scene
    warp = self
    selectOrCreateBoneForWarp(scene, warp)


def handleWarpNameChange(self, context):
    if not self.bl_update:
        return

    scene = context.scene
    warp = self

    currentBoneName = warp.boneName
    calculatedBoneName = shared.boneNameForWarp(warp)

    if currentBoneName != calculatedBoneName:
        bone, armatureObject = shared.findBoneWithArmatureObject(scene, currentBoneName)
        if bone is not None:
            bone.name = calculatedBoneName
            warp.boneName = bone.name
        else:
            warp.boneName = calculatedBoneName
    selectOrCreateBoneForWarp(scene, warp)


def handleCameraNameChange(self, context):
    scene = context.scene
    if self.name != self.oldName:
        bone, armatureObject = shared.findBoneWithArmatureObject(scene, self.oldName)
        if bone is not None:
            bone.name = self.name
    self.oldName = self.name


def handleDepthBlendFalloffChanged(self, context):
    material = self
    if material.depthBlendFalloff <= 0:
        if material.useDepthBlendFalloff:
            material.useDepthBlendFalloff = False
    else:
        if not material.useDepthBlendFalloff:
            material.useDepthBlendFalloff = True


def handleUseDepthBlendFalloffChanged(self, context):
    material = self
    if material.useDepthBlendFalloff:
        if material.depthBlendFalloff <= 0:
            material.depthBlendFalloff = shared.defaultDepthBlendFalloff
    else:
        if material.depthBlendFalloff != 0:
            material.depthBlendFalloff = 0


def handleMaterialNameChange(self, context):
    scene = context.scene
    materialName = self.name
    materialReferenceIndex = self.materialReferenceIndex
    if materialReferenceIndex != -1:
        materialReference = scene.m3_material_references[self.materialReferenceIndex]
        oldMaterialName = materialReference.name
        materialReference.name = materialName

        for particle_system in scene.m3_particle_systems:
            if particle_system.materialName == oldMaterialName:
                particle_system.materialName = materialName

        for projection in scene.m3_projections:
            if projection.materialName == oldMaterialName:
                projection.materialName = materialName

        for meshObject in shared.findMeshObjects(scene):
            mesh = meshObject.data
            if mesh.m3_material_name == oldMaterialName:
                mesh.m3_material_name = materialName


def handleAttachmentVolumeTypeChange(self, context):
    if not self.bl_update:
        return

    handleAttachmentPointNameOrTypeChange(self, context)
    if self.volumeType in ["0", "1", "2"]:
        if self.volumeSize0 == 0.0:
            self.volumeSize0 = 1.0
    else:
        self.volumeSize0 = 0.0

    if self.volumeType in ["0", "2"]:
        if self.volumeSize1 == 0.0:
            self.volumeSize1 = 1.0
    else:
        self.volumeSize1 = 0.0

    if self.volumeType in ["0"]:
        if self.volumeSize2 == 0.0:
            self.volumeSize2 = 1.0
    else:
        self.volumeSize2 = 0.0


def handleAttachmentVolumeSizeChange(self, context):
    if not self.bl_update:
        return

    scene = context.scene
    attachmentPoint = self
    selectOrCreateBoneForAttachmentPoint(scene, attachmentPoint)


def handleGeometricShapeUpdate(self, context):
    shapeObject = self
    selectOrCreateBoneForShapeObject(context.scene, shapeObject)


def handleParticleSystemsVisiblityUpdate(self, context):
    scene = context.scene
    for particleSystem in scene.m3_particle_systems:
        shared.setBoneVisibility(scene, particleSystem.boneName, self.showParticleSystems)

        for copy in particleSystem.copies:
            shared.setBoneVisibility(scene, copy.boneName, self.showParticleSystems)


def handleRibbonsVisiblityUpdate(self, context):
    scene = context.scene
    for ribbon in scene.m3_ribbons:
        shared.setBoneVisibility(scene, ribbon.boneName, self.showRibbons)

        # TODO for sub ribbons:
        # for subRibbon in ribbon.subRibbons:
        #     boneName = subRibbon.boneName
        #     shared.setBoneVisibility(scene, boneName, self.showRibbons)


def handleFuzzyHitTestVisiblityUpdate(self, context):
    scene = context.scene
    for fuzzyHitTest in scene.m3_fuzzy_hit_tests:
        shared.setBoneVisibility(scene, fuzzyHitTest.boneName, self.showFuzzyHitTests)


def handleTightHitTestVisiblityUpdate(self, context):
    scene = context.scene
    tightHitTest = scene.m3_tight_hit_test
    shared.setBoneVisibility(scene, tightHitTest.boneName, self.showTightHitTest)


def handleAttachmentPointVisibilityUpdate(self, context):
    scene = context.scene
    for attachmentPoint in scene.m3_attachment_points:
        shared.setBoneVisibility(scene, attachmentPoint.boneName, self.showAttachmentPoints)


def handleLightsVisiblityUpdate(self, context):
    scene = context.scene
    for light in scene.m3_lights:
        shared.setBoneVisibility(scene, light.boneName, self.showLights)


def handleForcesVisiblityUpdate(self, context):
    scene = context.scene
    for force in scene.m3_forces:
        shared.setBoneVisibility(scene, force.boneName, self.showForces)


def handleCamerasVisiblityUpdate(self, context):
    scene = context.scene
    for camera in scene.m3_cameras:
        boneName = camera.name
        shared.setBoneVisibility(scene, boneName, self.showCameras)


def handlePhysicsShapeVisibilityUpdate(self, context):
    scene = context.scene
    for rigidBody in scene.m3_rigid_bodies:
        shared.setBoneVisibility(scene, rigidBody.name, self.showPhysicsShapes)


def handleProjectionVisibilityUpdate(self, context):
    scene = context.scene
    for projection in scene.m3_projections:
        shared.setBoneVisibility(scene, projection.boneName, self.showProjections)


def handleWarpVisibilityUpdate(self, context):
    scene = context.scene
    for warp in scene.m3_warps:
        shared.setBoneVisibility(scene, warp.boneName, self.showWarps)


def handleAnimationSequenceStartFrameChange(self, context):
    context.scene.frame_start = self.startFrame


def handleAnimationSequenceEndFrameChange(self, context):
    context.scene.frame_end = self.exlusiveEndFrame - 1


def handleAnimationChange(ob, animation, prefix=""):
    animationData = ob.animation_data

    if animation:
        animationName = prefix + animation.name
        action = bpy.data.actions[animationName] if animationName in bpy.data.actions else bpy.data.actions.new(prefix + animation.name)
        action.id_root = shared.typeIdOfObject(ob)
        action.use_fake_user = True
    else:
        action = None

    prepareDefaultValuesForNewAction(ob, action)
    animationData.action = action


def handleAnimationSequenceIndexChange(self, context):
    scene = self

    animation = None
    if scene.m3_animation_index >= 0:
        animation = scene.m3_animations[scene.m3_animation_index]

        scene.frame_start = animation.startFrame
        scene.frame_current = scene.frame_start
        scene.frame_end = animation.exlusiveEndFrame - 1

    for ob in scene.objects:
        if ob.type == "ARMATURE":
            animationData = ob.animation_data
            if animationData is None:
                ob.animation_data_create()
            handleAnimationChange(ob, animation, prefix="Armature Object")

    if scene.animation_data is None:
        scene.animation_data_create()
    handleAnimationChange(scene, animation, prefix="Scene")


def handleAnimationSequenceNameChange(self, context):
    if "Armature Object" + self.nameOld in bpy.data.actions:
        bpy.data.actions["Armature Object" + self.nameOld].name = "Armature Object" + self.name
        bpy.data.actions["Scene" + self.nameOld].name = "Scene" + self.name
    self.nameOld = self.name


def prepareDefaultValuesForNewAction(objectWithAnimationData, newAction):
    oldAnimatedProperties = set()
    animationData = objectWithAnimationData.animation_data
    if animationData is None:
        raise Exception("Must have animation data")
    oldAction = animationData.action
    if oldAction is not None:
        for curve in oldAction.fcurves:
            oldAnimatedProperties.add((curve.data_path, curve.array_index))
    newAnimatedProperties = set()
    if newAction is not None:
        for curve in newAction.fcurves:
            newAnimatedProperties.add((curve.data_path, curve.array_index))
    defaultAction = shared.getOrCreateDefaultActionFor(objectWithAnimationData)

    removedProperties = set()

    propertiesBecomingAnimated = newAnimatedProperties.difference(oldAnimatedProperties)
    for prop in propertiesBecomingAnimated:
        try:
            value = getAttribute(objectWithAnimationData, prop[0], prop[1])
            propertyExists = True
        except:
            propertyExists = False
        if propertyExists:
            shared.setDefaultValue(defaultAction, prop[0], prop[1], value)
        else:
            # mlog.debug("Can't find prop %s" % prop[0], prop[1])
            removedProperties.add(prop)
    propertiesBecomingUnanimated = oldAnimatedProperties.difference(newAnimatedProperties)

    if len(removedProperties) > 0:
        mlog.debug("Removing animations for %s since those properties do no longer exist" % removedProperties)

    removedCurves = list()
    if newAction is not None:
        for curve in newAction.fcurves:
            if (curve.data_path, curve.array_index) in removedProperties:
                removedCurves.append(curve)
    for removedCurve in removedCurves:
        newAction.fcurves.remove(removedCurve)

    defaultsToRemove = set()

    for curve in defaultAction.fcurves:
        prop = (curve.data_path, curve.array_index)
        if prop in propertiesBecomingUnanimated:
            defaultValue = curve.evaluate(0)
            curvePath = curve.data_path
            curveIndex = curve.array_index

            try:
                resolvedObject = objectWithAnimationData.path_resolve(curvePath)
                propertyExists = True
            except:
                propertyExists = False
            if propertyExists:
                if type(resolvedObject) in [float, int, bool]:
                    dotIndex = curvePath.rfind(".")
                    attributeName = curvePath[dotIndex + 1:]
                    resolvedObject = objectWithAnimationData.path_resolve(curvePath[:dotIndex])
                    setattr(resolvedObject, attributeName, defaultValue)
                else:
                    resolvedObject[curveIndex] = defaultValue
            else:
                defaultsToRemove.add(prop)
    removedDefaultCurves = list()
    for curve in defaultAction.fcurves:
        if (curve.data_path, curve.array_index) in removedProperties:
            removedDefaultCurves.append(curve)
    for removedDefaultCurve in removedDefaultCurves:
        defaultAction.fcurves.remove(removedDefaultCurve)


def getAttribute(obj, curvePath, curveIndex):
    """Gets the value of an attribute via animation path and index"""
    obj = obj.path_resolve(curvePath)
    if type(obj) in [float, int, bool]:
        return obj
    else:
        return obj[curveIndex]


def handleParticleSystemIndexChanged(self, context):
    scene = context.scene
    if scene.m3_particle_system_index == -1:
        return
    particleSystem = scene.m3_particle_systems[scene.m3_particle_system_index]
    particleSystem.copyIndex = -1
    selectOrCreateBoneForParticleSystem(scene, particleSystem)


def handleRibbonIndexChanged(self, context):
    scene = context.scene
    if scene.m3_ribbon_index == -1:
        return
    ribbon = scene.m3_ribbons[scene.m3_ribbon_index]
    ribbon.endPointIndex = -1
    selectOrCreateBoneForRibbon(scene, ribbon)


def handleRibbonEndPointIndexChanged(self, context):
    scene = context.scene
    ribbon = self
    if ribbon.endPointIndex >= 0 and ribbon.endPointIndex < len(ribbon.endPoints):
        endPoint = ribbon.endPoints[ribbon.endPointIndex]
        selectBoneIfItExists(scene, endPoint.name)


def handleForceIndexChanged(self, context):
    scene = context.scene
    if scene.m3_force_index == -1:
        return
    force = scene.m3_forces[scene.m3_force_index]
    selectOrCreateBoneForForce(scene, force)


def handlePhysicsShapeUpdate(self, context):
    scene = context.scene

    if scene.m3_rigid_body_index != -1:
        rigidBody = scene.m3_rigid_bodies[scene.m3_rigid_body_index]
        shared.updateBoneShapeOfRigidBody(scene, rigidBody, rigidBody.name)

    selectCurrentRigidBodyBone(scene)
    scene.m3_bone_visiblity_options.showPhysicsShapes = True


def handleRigidBodyIndexChange(self, context):
    scene = context.scene
    scene.m3_bone_visiblity_options.showPhysicsShapes = True
    selectCurrentRigidBodyBone(scene)


def handleRigidBodyBoneChange(self, context):
    scene = context.scene
    selectCurrentRigidBodyBone(scene)
    shared.removeRigidBodyBoneShape(scene, self.nameOld)
    shared.updateBoneShapeOfRigidBody(scene, self, self.name)
    self.nameOld = self.name


def selectCurrentRigidBodyBone(scene):
    if scene.m3_rigid_body_index != -1:
        rigidBody = scene.m3_rigid_bodies[scene.m3_rigid_body_index]
        selectBone(scene, rigidBody.name)


def handleLightIndexChanged(self, context):
    scene = context.scene
    if scene.m3_light_index == -1:
        return
    light = scene.m3_lights[scene.m3_light_index]
    selectOrCreateBoneForLight(scene, light)


def handleBillboardBehaviorIndexChanged(self, context):
    scene = context.scene
    if scene.m3_billboard_behavior_index == -1:
        return
    billboardBehavior = scene.m3_billboard_behaviors[scene.m3_billboard_behavior_index]
    selectBoneIfItExists(scene, billboardBehavior.name)


def handleTurretBehaviorPartIndexChanged(self, context):
    scene = context.scene
    if scene.m3_turret_behavior_index < 0:
        return
    turret = scene.m3_turret_behaviors[scene.m3_turret_behavior_index]
    if turret.part_index < 0:
        return
    part = turret.parts[turret.part_index]
    selectBoneIfItExists(scene, part.name)


def handleIkChainIndexChanged(self, context):
    scene = context.scene
    if scene.m3_ik_chain_index == -1:
        return
    ik = scene.m3_ik_chains[scene.m3_ik_chain_index]
    shared.selectBonesIfTheyExist(scene, [ik.boneName1, ik.boneName2])


def setPhysicsJointPivot(scene, name, boneName, offset, rotation):

    bone, armature = shared.findBoneWithArmatureObject(scene, boneName)

    if bone:
        if name not in bpy.data.objects:
            empty = bpy.data.objects.new(name, None)
            scene.collection.objects.link(empty)
            empty.show_in_front = True
            empty.empty_display_type = "ARROWS"
            empty.empty_display_size = 0.4
        else:
            empty = bpy.data.objects[name]

        matrix = bone.matrix_local + shared.composeMatrix(offset, rotation, (1, 1, 1))
        loc, rot, scale = matrix.decompose()

        empty.parent = armature
        empty.location = loc
        empty.rotation_euler = rot.to_euler("XYZ")


def handlePhysicsJointPivotDisplay(self, context):
    name1 = "M3PhysicsJointPivotHelper1"
    name2 = "M3PhysicsJointPivotHelper2"
    obs = bpy.data.objects
    scene = context.scene

    if scene.m3_physics_joint_index >= 0 and scene.m3_physics_joint_pivots:
        pj = scene.m3_physics_joints[scene.m3_physics_joint_index]

        if pj.bl_update:
            setPhysicsJointPivot(scene, name1, pj.boneName1, pj.offset1, pj.rotation1)
            setPhysicsJointPivot(scene, name2, pj.boneName2, pj.offset2, pj.rotation2)

    else:
        if name1 in obs:
            obs.remove(bpy.data.objects[name1], do_unlink=True)

        if name2 in obs:
            obs.remove(bpy.data.objects[name2], do_unlink=True)


def handlePhysicsJointIndexChanged(self, context):
    if self.m3_physics_joint_index >= 0:
        pj = self.m3_physics_joints[self.m3_physics_joint_index]
        shared.selectBonesIfTheyExist(self, [pj.boneName1, pj.boneName2])
    handlePhysicsJointPivotDisplay(self, context)


def handleWarpIndexChanged(self, context):
    scene = context.scene
    if scene.m3_warp_index == -1:
        return
    warp = scene.m3_warps[scene.m3_warp_index]
    selectOrCreateBoneForWarp(scene, warp)


def handleAttachmentPointIndexChanged(self, context):
    scene = context.scene
    if scene.m3_attachment_point_index == -1:
        return
    attachmentPoint = scene.m3_attachment_points[scene.m3_attachment_point_index]
    selectOrCreateBoneForAttachmentPoint(scene, attachmentPoint)


def handleParticleSystemCopyIndexChanged(self, context):
    scene = context.scene
    particleSystem = self
    if particleSystem.copyIndex >= 0 and particleSystem.copyIndex < len(particleSystem.copies):
        copy = particleSystem.copies[particleSystem.copyIndex]
        selectOrCreateBoneForParticleSystemCopy(scene, particleSystem, copy)


def handleCameraIndexChanged(self, context):
    scene = context.scene
    if scene.m3_camera_index == -1:
        return
    camera = scene.m3_cameras[scene.m3_camera_index]
    selectOrCreateBoneForCamera(scene, camera)


def handleFuzzyHitTestIndexChanged(self, context):
    scene = context.scene
    if scene.m3_fuzzy_hit_test_index == -1:
        return
    fuzzyHitTest = scene.m3_fuzzy_hit_tests[scene.m3_fuzzy_hit_test_index]
    selectOrCreateBoneForShapeObject(scene, fuzzyHitTest)


def selectOrCreateBoneForAttachmentPoint(scene, attachmentPoint):
    scene.m3_bone_visiblity_options.showAttachmentPoints = True
    boneName = attachmentPoint.boneName
    bone, poseBone = selectOrCreateBone(scene, boneName)
    shared.updateBoneShapeOfAttachmentPoint(attachmentPoint, bone, poseBone)


def selectOrCreateBoneForParticleSystemCopy(scene, particleSystem, copy):
    scene.m3_bone_visiblity_options.showParticleSystems = True
    boneName = copy.boneName
    bone, poseBone = selectOrCreateBone(scene, boneName)
    shared.updateBoneShapeOfParticleSystem(particleSystem, bone, poseBone)


def selectOrCreateBoneForForce(scene, force):
    scene.m3_bone_visiblity_options.showForces = True
    boneName = force.boneName
    bone, poseBone = selectOrCreateBone(scene, boneName)
    shared.updateBoneShapeOfForce(force, bone, poseBone)
    return (bone, poseBone)


def selectOrCreateBoneForLight(scene, light):
    scene.m3_bone_visiblity_options.showLights = True
    boneName = light.boneName
    bone, poseBone = selectOrCreateBone(scene, boneName)
    shared.updateBoneShapeOfLight(light, bone, poseBone)


def selectOrCreateBoneForWarp(scene, projection):
    scene.m3_bone_visiblity_options.showWarps = True
    boneName = projection.boneName
    bone, poseBone = selectOrCreateBone(scene, boneName)
    shared.updateBoneShapeOfWarp(projection, bone, poseBone)


def selectOrCreateBoneForCamera(scene, camera):
    scene.m3_bone_visiblity_options.showCameras = True
    selectOrCreateBone(scene, camera.name)


def selectOrCreateBoneForParticleSystem(scene, particle_system):
    scene.m3_bone_visiblity_options.showParticleSystems = True
    boneName = particle_system.boneName
    bone, poseBone = selectOrCreateBone(scene, boneName)
    shared.updateBoneShapeOfParticleSystem(particle_system, bone, poseBone)


def selectOrCreateBoneForRibbon(scene, ribbon):
    scene.m3_bone_visiblity_options.showRibbons = True
    boneName = ribbon.boneName
    bone, poseBone = selectOrCreateBone(scene, boneName)
    shared.updateBoneShapeOfRibbon(ribbon, bone, poseBone)


def selectOrCreateBoneForShapeObject(scene, shapeObject):
    boneName = shapeObject.boneName
    if boneName == shared.tightHitTestBoneName:
        scene.m3_bone_visiblity_options.showTightHitTest = True
    else:
        scene.m3_bone_visiblity_options.showFuzzyHitTests = True
    bone, poseBone = selectOrCreateBone(scene, boneName)
    shared.updateBoneShapeOfShapeObject(shapeObject, bone, poseBone)


def determineLayerNames(defaultSetting):
    from . import m3
    settingToStructureNameMap = {
        defaultSettingMesh: "MAT_",
        defaultSettingParticle: "MAT_",
        defaultSettingCreep: "CREP",
        defaultSettingDisplacement: "DIS_",
        defaultSettingComposite: "CMP_",
        defaultSettingVolume: "VOL_",
        defaultSettingVolumeNoise: "VON_",
        defaultSettingTerrain: "TER_",
        defaultSettingSplatTerrainBake: "STBM",
        defaultSettingLensFlare: "LFLR"
    }
    structureName = settingToStructureNameMap[defaultSetting]
    structureDescription = m3.structures[structureName].getNewestVersion()
    for field in structureDescription.fields:
        if hasattr(field, "referenceStructureDescription"):
            if field.historyOfReferencedStructures.name == "LAYR":
                yield shared.getLayerNameFromFieldName(field.name)


def createMaterial(scene, materialName, defaultSetting):
    layerNames = determineLayerNames(defaultSetting)

    if defaultSetting in [defaultSettingMesh, defaultSettingParticle]:
        materialType = shared.standardMaterialTypeIndex
        materialIndex = len(scene.m3_standard_materials)
        material = scene.m3_standard_materials.add()
        for layerName in layerNames:
            layer = material.layers.add()
            layer.name = layerName
            if layerName == "Diffuse":
                if defaultSetting != defaultSettingParticle:
                    layer.colorChannelSetting = shared.colorChannelSettingRGBA

        if defaultSetting == defaultSettingParticle:
            material.unfogged = True
            material.blendMode = "2"
            material.layerBlendType = "2"
            material.emisBlendType = "2"
            material.noShadowsCast = True
            material.noHitTest = True
            material.noShadowsReceived = True
            material.transparentShadows = True
            material.useDepthBlendFalloff = True
            material.depthBlendFalloff = shared.defaultDepthBlendFalloff
            material.unknownFlag0x2 = True
            material.unknownFlag0x8 = True
    elif defaultSetting == defaultSettingDisplacement:
        materialType = shared.displacementMaterialTypeIndex
        materialIndex = len(scene.m3_displacement_materials)
        material = scene.m3_displacement_materials.add()
        for layerName in layerNames:
            layer = material.layers.add()
            layer.name = layerName
    elif defaultSetting == defaultSettingComposite:
        materialType = shared.compositeMaterialTypeIndex
        materialIndex = len(scene.m3_composite_materials)
        material = scene.m3_composite_materials.add()
        # has no layers
    elif defaultSetting == defaultSettingTerrain:
        materialType = shared.terrainMaterialTypeIndex
        materialIndex = len(scene.m3_terrain_materials)
        material = scene.m3_terrain_materials.add()
        for layerName in layerNames:
            layer = material.layers.add()
            layer.name = layerName
    elif defaultSetting == defaultSettingVolume:
        materialType = shared.volumeMaterialTypeIndex
        materialIndex = len(scene.m3_volume_materials)
        material = scene.m3_volume_materials.add()
        for layerName in layerNames:
            layer = material.layers.add()
            layer.name = layerName
    elif defaultSetting == defaultSettingVolumeNoise:
        materialType = shared.volumeNoiseMaterialTypeIndex
        materialIndex = len(scene.m3_volume_noise_materials)
        material = scene.m3_volume_noise_materials.add()
        for layerName in layerNames:
            layer = material.layers.add()
            layer.name = layerName
    elif defaultSetting == defaultSettingCreep:
        materialType = shared.creepMaterialTypeIndex
        materialIndex = len(scene.m3_creep_materials)
        material = scene.m3_creep_materials.add()
        for layerName in layerNames:
            layer = material.layers.add()
            layer.name = layerName
    elif defaultSetting == defaultSettingSplatTerrainBake:
        materialType = shared.stbMaterialTypeIndex
        materialIndex = len(scene.m3_stb_materials)
        material = scene.m3_stb_materials.add()
        for layerName in layerNames:
            layer = material.layers.add()
            layer.name = layerName
    elif defaultSetting == defaultSettingLensFlare:
        materialType = shared.lensFlareMaterialTypeIndex
        materialIndex = len(scene.m3_lens_flare_materials)
        material = scene.m3_lens_flare_materials.add()
        for layerName in layerNames:
            layer = material.layers.add()
            layer.name = layerName

    materialReferenceIndex = len(scene.m3_material_references)
    materialReference = scene.m3_material_references.add()
    materialReference.materialIndex = materialIndex
    materialReference.materialType = materialType
    material.materialReferenceIndex = materialReferenceIndex
    material.name = materialName  # will also set materialReference name

    scene.m3_material_reference_index = len(scene.m3_material_references) - 1


emissionAreaTypesWithRadius = [
    shared.emissionAreaTypeSphere,
    shared.emissionAreaTypeCylinder,
    shared.emissionAreaTypeDisc,
]
emissionAreaTypesWithWidth = [
    shared.emissionAreaTypePlane,
    shared.emissionAreaTypeCuboid,
]
emissionAreaTypesWithLength = [
    shared.emissionAreaTypePlane,
    shared.emissionAreaTypeCuboid,
]
emissionAreaTypesWithHeight = [
    shared.emissionAreaTypeCuboid,
    shared.emissionAreaTypeCylinder,
]
emissionAreaTypeList = [
    (shared.emissionAreaTypePoint, "Point", "Particles spawn at a certain point"),
    (shared.emissionAreaTypePlane, "Plane", "Particles spawn in a rectangle"),
    (shared.emissionAreaTypeSphere, "Sphere", "Particles spawn in a sphere"),
    (shared.emissionAreaTypeCuboid, "Cuboid", "Particles spawn in a cuboid"),
    (shared.emissionAreaTypeCylinder, "Cylinder", "Particles spawn in a cylinder"),
    (shared.emissionAreaTypeDisc, "Disc", "Particles spawn in a cylinder of height 0"),
    (shared.emissionAreaTypeMesh, "Spline", "Spawn location are the vertices of a mesh"),
    ("7", "Mesh", "If Vertex Color is applied and exported by the material on the mesh, then the Red channel of vertex color regulates the probability that a face will be used for particle emission")
]

particleTypeList = [
    ("0", "Square Billbords", "Quads always rotated towards camera (id 0)"),
    ("1", "Speed Scaled and Rotated Billbords", "Particles are rectangles scaled which get scaled by speed by a configurable amounth"),
    ("2", "Square Billbords 2?", "Unknown 2"),
    ("3", "Square Billbords 3?", "Unknown 3"),
    ("4", "Square Billbords 4?", "Unknown 4"),
    ("5", "Square Billbords 5?", "Unknown 5"),
    ("6", "Rectangular Billbords", "Rectangles which can have a length != witdh which are rotated towards the camera"),
    ("7", "Quads with speed as normal", "Particles are quads which have their normals aligned to the speed vector of the particle"),
    ("8", "Unknown (Id 8)", "Code 8 with unknown meaning"),
    ("9", "Ray from Spawn Location", "A billboard that reaches from the spawn location to the current position"),
    ("10", "Unknown (Id 10)", "Code 10 with unknown meaning")
]

ribbonTypeList = [
    ("0", "Planar Billboarded", "Planar Billboarded"),
    ("1", "Planar", "Planar"),
    ("2", "Cylinder", "Cylinder"),
    ("3", "Star Shaped", "Star Shaped")
]

ribbonCullType = [
    ("0", "Lifespan", "Ribbon elements are destroyed after having existed for the specified lifespan."),
    ("1", "Length Based", "Ribbon elements are destroyed after reaching the specified maximum length"),
]

ribbonCurveType = [
    ("0", "None", ""),
    ("1", "Sin", ""),
    ("2", "Cos", ""),
    ("3", "Saw Tooth", ""),
    ("4", "Square Wave", ""),
    ("5", "Random Noise", ""),
    ("6", "Continous Noise", ""),
]

forceTypeList = [
    ("0", "Directional", "The particles get accelerated into one direction"),
    ("1", "Radial", "Particles get accelerated ayway from the force source"),
    ("2", "Dampening", "This is a drag operation that resists the movement of particles"),
    ("3", "Vortex", "This is a special rotation field that brings particles into a orbit. Does not work with Box Shape applied.")
]

forceShapeList = [
    ("0", "Sphere", "The particles get accelerated into one direction"),
    ("1", "Cylinder", "A cylinder with Radius and Height"),
    ("2", "Box", "A box shape with Width, Height, and Length."),
    ("3", "Hemisphere", "Half sphere shape defined with Radius."),
    ("4", "ConeDome", "Special cone shape with length defined as Radius and cone width defined as Angle.")
]

physicsShapeTypeList = [
    ("0", "Box", "Box shape with the given width, length and height"),
    ("1", "Sphere", "Sphere shape with the given radius"),
    ("2", "Capsule", "Capsule shape with the given radius and length"),
    ("3", "Cylinder", "Cylinder with the given radius and length"),
    ("4", "Convex Hull", "Convex hull created from the attached mesh"),
    ("5", "Mesh", "Mesh shape created from the attached mesh"),
]

particleEmissionTypeList = [
    ("0", "Constant", "Emitted particles fly towards a configureable direction with a configurable spread"),
    ("1", "Radial", "Particles move into all kinds of directions"),
    ("2", "Z Axis", "Picks randomly to move in the direction of the positive or negative local Z-Axis for the emitter.e"),
    ("3", "Random", "Picks an entirely arbitrary orientation."),
    ("4", "Mesh Normal", "when using a Mesh Emitter Shape, uses the normal of the face being emitted from as the direction vector.")
]

animationSmoothTypeList = [
    ("0", "Linear", "Linear transitions without usage of hold time"),
    ("1", "Smooth", "Smooth transitions without usage of hold time"),
    ("2", "Bezier", "Bezier transitions without usage of hold time"),
    ("3", "Linear Hold", "Linear transitions with usage of hold time"),
    ("4", "Bezier Hold", "Bezier transitions with usage of hold time")
]

attachmentVolumeTypeList = [
    (shared.attachmentVolumeNone, "None", "No Volume, it's a simple attachment point"),
    (shared.attachmentVolumeCuboid, "Cuboid", "Volume with the shape of a cuboid with the given width, length and height"),
    (shared.attachmentVolumeSphere, "Sphere", "Volume with the shape of a sphere with the given radius"),
    (shared.attachmentVolumeCapsule, "Capsule", "Volume with the shape of a cylinder with the given radius and height"),
    ("3", "Unknown 3", "Unknown Volume with id 3"),
    ("4", "Unknown 4", "Unknown Volume with id 4")
]

geometricShapeTypeList = [
    ("0", "Cuboid", "A cuboid with the given width, length and height"),
    ("1", "Sphere", "A sphere with the given radius"),
    ("2", "Capsule", "A capsule with the given radius and height"),
]

physicsJointType = [
    ("0", "Spherical", "Allows the joint to move freely on any axis"),
    ("1", "Revolute", "Allows the joint to move only on the Z axis, like a door hinge"),
    ("2", "Cone", "Allows the joint to move to move freely like a spherical joint, but constrains movement to the cone angle, around the Z axis"),
    ("3", "Weld", "Restricts the joint's rotation, but is not perfectly rigid")
]

defaultSettingMesh = "MESH"
defaultSettingParticle = "PARTICLE"
defaultSettingDisplacement = "DISPLACEMENT"
defaultSettingComposite = "COMPOSITE"
defaultSettingTerrain = "TERRAIN"
defaultSettingVolume = "VOLUME"
defaultSettingVolumeNoise = "VOLUME_NOISE"
defaultSettingCreep = "CREEP"
defaultSettingSplatTerrainBake = "STB"
defaultSettingLensFlare = "LENS_FLARE"

matDefaultSettingsList = [
    (defaultSettingMesh, "Mesh Standard Material", "A material for meshes"),
    (defaultSettingParticle, "Particle Standard Material", "Material for particle systems"),
    (defaultSettingDisplacement, "Displacement Material", "Moves the colors of the background to other locations"),
    (defaultSettingComposite, "Composite Material", "A combination of multiple materials"),
    (defaultSettingTerrain, "Terrain Material", "Makes the object look like the ground below it"),
    (defaultSettingVolume, "Volume Material", "A fog like material"),
    (defaultSettingVolumeNoise, "Volume Noise Material", "A fog like material"),
    (defaultSettingCreep, "Creep Material", "Looks like creep if there is creep below the model and is invisible otherwise"),
    (defaultSettingSplatTerrainBake, "STB Material", "Splat Terrain Bake Material"),
    (defaultSettingLensFlare, "Lens Flare Material", "Lens flare material which can not be exported yet"),
]

billboardBehaviorTypeList = [
    ("0", "Local X", "Bone gets oriented around X towards the camera, but rotates then with the model"),
    ("1", "Local Z", "Bone gets oriented around Z towards the camera, but rotates then with the model"),
    ("2", "Local Y", "Bone gets oriented around Y towards the camera, but rotates then with the model"),
    ("3", "World X", "Bone gets oriented around X towards the camera, independent of model rotation"),
    ("4", "World Z", "Bone gets oriented around Z towards the camera, independent of model rotation"),
    ("5", "World Y", "Bone gets oriented around Y towards the camera, independent of model rotation"),
    ("6", "World All", "Bone orients itself towards the camera and rotates around all axes to do so")
]

matBlendModeList = [
    ("0", "Opaque", "no description yet"),
    ("1", "Alpha Blend", "no description yet"),
    ("2", "Add", "no description yet"),
    ("3", "Alpha Add", "no description yet"),
    ("4", "Mod", "no description yet"),
    ("5", "Mod 2x", "no description yet"),
    ("6", "Unknown 0x06", "no description yet"),
    ("7", "Unknown 0x07", "no description yet"),
]

matLayerAndEmisBlendModeList = [
    ("0", "Mod", "no description yet"),
    ("1", "Mod 2x", "no description yet"),
    ("2", "Add", "no description yet"),
    ("3", "Blend", "no description yet"),
    ("4", "Team Color Emissive Add", "no description yet"),
    ("5", "Team Color Diffuse Add", "no description yet")
]

matSpecularTypeList = [
    ("0", "RGB", "no description yet"),
    ("1", "Alpha Only", "no description yet")
]

lightTypeList = [
    # directional light isn"t supported yet: ("0", "Directional", ""),
    (shared.lightTypePoint, "Point", "Light are generated around a point"),
    (shared.lightTypeSpot, "Spot", "")
]


class M3AnimIdData(bpy.types.PropertyGroup):
    # animId is an unsigned integer, but Blender can store only signed ones
    # So, the number range needs to be moved into the negative for storage
    animIdMinus2147483648: bpy.props.IntProperty(options=set())
    longAnimId: bpy.props.StringProperty(options=set())


class M3AnimatedPropertyReference(bpy.types.PropertyGroup):
    longAnimId: bpy.props.StringProperty(options=set())


class M3TransformationCollection(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="all")
    animatedProperties: bpy.props.CollectionProperty(options=set(), type=M3AnimatedPropertyReference)
    runsConcurrent: bpy.props.BoolProperty(options=set(), default=True)
    priority: bpy.props.IntProperty(options=set(), subtype="UNSIGNED")


class M3Animation(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="Stand", update=handleAnimationSequenceNameChange)
    nameOld: bpy.props.StringProperty(options=set(), default="Stand")
    startFrame: bpy.props.IntProperty(options=set(), subtype="UNSIGNED", update=handleAnimationSequenceStartFrameChange)
    useSimulateFrame: bpy.props.BoolProperty(options=set(), default=False)
    simulateFrame: bpy.props.IntProperty(options=set(), subtype="UNSIGNED", default=0)
    exlusiveEndFrame: bpy.props.IntProperty(options=set(), subtype="UNSIGNED", update=handleAnimationSequenceEndFrameChange)
    transformationCollections: bpy.props.CollectionProperty(options=set(), type=M3TransformationCollection)
    transformationCollectionIndex: bpy.props.IntProperty(options=set(), default=0)
    movementSpeed: bpy.props.FloatProperty(options=set())
    frequency: bpy.props.IntProperty(options=set(), subtype="UNSIGNED")
    notLooping: bpy.props.BoolProperty(options=set())
    alwaysGlobal: bpy.props.BoolProperty(options=set())
    globalInPreviewer: bpy.props.BoolProperty(options=set())


class M3StandardMaterial(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="Material", update=handleMaterialNameChange)
    # the following field gets used to update the name of the material reference:
    materialReferenceIndex: bpy.props.IntProperty(options=set(), default=-1)
    layers: bpy.props.CollectionProperty(options=set(), type=cm.M3MaterialLayer)
    blendMode: bpy.props.EnumProperty(options=set(), items=matBlendModeList, default="0")
    priority: bpy.props.IntProperty(
        options=set(),
        description=f"""\
Defines the sorting relationship between this material and other transparent materials in the model file. Within a given model, materials are drawn in order from highest priority value to lowest. Sorting for materials of equal priority is undefined. Priorities have no effect across multiple models."""
    )
    specularity: bpy.props.FloatProperty(options=set())
    cutoutThresh: bpy.props.IntProperty(options=set(), min=0, max=255, default=0)
    specMult: bpy.props.FloatProperty(options=set(), default=1)
    emisMult: bpy.props.FloatProperty(options=set(), default=1)
    envConstMult: bpy.props.FloatProperty(options=set(), default=1.0)
    envDiffMult: bpy.props.FloatProperty(options=set(), default=0.0)
    envSpecMult: bpy.props.FloatProperty(options=set(), default=0.0)
    layerBlendType: bpy.props.EnumProperty(options=set(), items=matLayerAndEmisBlendModeList, default="2")
    emisBlendType: bpy.props.EnumProperty(options=set(), items=matLayerAndEmisBlendModeList, default="2")
    emisMode: bpy.props.EnumProperty(options=set(), items=matLayerAndEmisBlendModeList, default="2")  # what is the difference between emisBlendType and emisMode?
    specType: bpy.props.EnumProperty(options=set(), items=matSpecularTypeList, default="0")
    parallaxHeight: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=0.0)
    unfogged: bpy.props.BoolProperty(options=set(), default=True)
    twoSided: bpy.props.BoolProperty(options=set(), default=False)
    unshaded: bpy.props.BoolProperty(options=set(), default=False)
    noShadowsCast: bpy.props.BoolProperty(options=set(), default=False)
    noHitTest: bpy.props.BoolProperty(options=set(), default=False)
    noShadowsReceived: bpy.props.BoolProperty(options=set(), default=False)
    depthPrepass: bpy.props.BoolProperty(options=set(), default=False)
    useTerrainHDR: bpy.props.BoolProperty(options=set(), default=False)
    unknown0x400: bpy.props.BoolProperty(options=set(), default=False)
    simulateRoughness: bpy.props.BoolProperty(options=set(), default=False)
    perPixelForwardLighting: bpy.props.BoolProperty(options=set(), default=False)
    depthFog: bpy.props.BoolProperty(options=set(), default=False)
    transparentShadows: bpy.props.BoolProperty(options=set(), default=False)
    decalLighting: bpy.props.BoolProperty(options=set(), default=False)
    transparencyDepthEffects: bpy.props.BoolProperty(options=set(), default=False)
    transparencyLocalLights: bpy.props.BoolProperty(options=set(), default=False)
    disableSoft: bpy.props.BoolProperty(options=set(), default=False)
    darkNormalMapping: bpy.props.BoolProperty(options=set(), default=False)
    hairLayerSorting: bpy.props.BoolProperty(options=set(), default=False)
    acceptSplats: bpy.props.BoolProperty(options=set(), default=False)
    decalRequiredOnLowEnd: bpy.props.BoolProperty(options=set(), default=False)
    emissiveRequiredOnLowEnd: bpy.props.BoolProperty(options=set(), default=False)
    specularRequiredOnLowEnd: bpy.props.BoolProperty(options=set(), default=False)
    acceptSplatsOnly: bpy.props.BoolProperty(options=set(), default=False)
    backgroundObject: bpy.props.BoolProperty(options=set(), default=False)
    unknown0x8000000: bpy.props.BoolProperty(options=set(), default=False)
    zpFillRequiredOnLowEnd: bpy.props.BoolProperty(options=set(), default=False)
    excludeFromHighlighting: bpy.props.BoolProperty(options=set(), default=False)
    clampOutput: bpy.props.BoolProperty(options=set(), default=False)
    geometryVisible: bpy.props.BoolProperty(options=set(), default=True)
    depthBlendFalloff: bpy.props.FloatProperty(
        options=set(), update=handleDepthBlendFalloffChanged, default=0,
        description=f"""\
Extends the distance over which particle effects fade out when they get close to a solid object. To reduce visual clipping artifacts, particle effects in StarCraft II fade out as they get close to another surface. Increasing this value causes the blend to happen over a wider range. Disable Soft (Depth Blend) can bypass this effect when no depth blend is desired.
        """
    )
    useDepthBlendFalloff: bpy.props.BoolProperty(options=set(), update=handleUseDepthBlendFalloffChanged, description="Should be true for particle system materials", default=False)
    useVertexColor: bpy.props.BoolProperty(options=set(), description="The vertex color layer named color will be used to tint the model", default=False)
    useVertexAlpha: bpy.props.BoolProperty(options=set(), description="The vertex color layer named alpha, will be used to determine the alpha of the model", default=False)
    unknownFlag0x200: bpy.props.BoolProperty(options=set())


class M3DisplacementMaterial(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="Material", update=handleMaterialNameChange)
    # the following field gets used to update the name of the material reference:
    materialReferenceIndex: bpy.props.IntProperty(options=set(), default=-1)
    strengthFactor: bpy.props.FloatProperty(name="strength factor", options={"ANIMATABLE"}, default=1, description="Factor that gets multiplied with the strength values")
    layers: bpy.props.CollectionProperty(options=set(), type=cm.M3MaterialLayer)
    priority: bpy.props.IntProperty(options=set())


class M3CompositeMaterialSection(bpy.types.PropertyGroup):
    # The material name is getting called "name" so that blender names it properly in the list view
    name: bpy.props.StringProperty(options=set(), )
    alphaFactor: bpy.props.FloatProperty(name="alphaFactor", options={"ANIMATABLE"}, min=0, max=1, default=1, description="Defines the factor with which the alpha channel gets multiplied")


class M3CompositeMaterial(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="Material", update=handleMaterialNameChange)
    # the following field gets used to update the name of the material reference:
    materialReferenceIndex: bpy.props.IntProperty(options=set(), default=-1)
    layers: bpy.props.CollectionProperty(options=set(), type=cm.M3MaterialLayer)
    sections: bpy.props.CollectionProperty(options=set(), type=M3CompositeMaterialSection)
    sectionIndex: bpy.props.IntProperty(options=set(), default=0)


class M3TerrainMaterial(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="Material", update=handleMaterialNameChange)
    # the following field gets used to update the name of the material reference:
    materialReferenceIndex: bpy.props.IntProperty(options=set(), default=-1)
    layers: bpy.props.CollectionProperty(options=set(), type=cm.M3MaterialLayer)


class M3VolumeMaterial(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="Material", update=handleMaterialNameChange)
    # the following field gets used to update the name of the material reference:
    materialReferenceIndex: bpy.props.IntProperty(options=set(), default=-1)
    volumeDensity: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=0.3, description="Factor that gets multiplied with the strength values")
    layers: bpy.props.CollectionProperty(options=set(), type=cm.M3MaterialLayer)


class M3VolumeNoiseMaterial(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="Material", update=handleMaterialNameChange)
    # the following field gets used to update the name of the material reference:
    materialReferenceIndex: bpy.props.IntProperty(options=set(), default=-1)
    volumeDensity: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=0.3, description="Factor that gets multiplied with the strength values")
    nearPlane: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=0)
    falloff: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=0.9)
    layers: bpy.props.CollectionProperty(options=set(), type=cm.M3MaterialLayer)
    scrollRate: bpy.props.FloatVectorProperty(default=(0, 0, 0.8), size=3, subtype="XYZ", options={"ANIMATABLE"})
    translation: bpy.props.FloatVectorProperty(default=(0, 0, 0), size=3, subtype="XYZ", options={"ANIMATABLE"})
    scale: bpy.props.FloatVectorProperty(default=(2, 2, 1), size=3, subtype="XYZ", options={"ANIMATABLE"})
    rotation: bpy.props.FloatVectorProperty(default=(0, 0, 0), size=3, subtype="XYZ", options={"ANIMATABLE"})
    alphaTreshhold: bpy.props.IntProperty(options=set(), default=0)
    drawAfterTransparency: bpy.props.BoolProperty(options=set(), default=False)


class M3CreepMaterial(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="Material", update=handleMaterialNameChange)
    # the following field gets used to update the name of the material reference:
    materialReferenceIndex: bpy.props.IntProperty(options=set(), default=-1)
    layers: bpy.props.CollectionProperty(options=set(), type=cm.M3MaterialLayer)


class M3STBMaterial(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="Material", update=handleMaterialNameChange)
    # the following field gets used to update the name of the material reference:
    materialReferenceIndex: bpy.props.IntProperty(options=set(), default=-1)
    layers: bpy.props.CollectionProperty(options=set(), type=cm.M3MaterialLayer)


class M3LensFlareMaterial(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="Material", update=handleMaterialNameChange)
    # the following field gets used to update the name of the material reference:
    materialReferenceIndex: bpy.props.IntProperty(options=set(), default=-1)
    layers: bpy.props.CollectionProperty(options=set(), type=cm.M3MaterialLayer)


class M3MaterialNode(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="Material", update=handleMaterialNameChange)
    # the following field gets used to update the name of the material reference:
    materialReferenceIndex: bpy.props.IntProperty(options=set(), default=-1)


class M3Camera(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), update=handleCameraNameChange)
    oldName: bpy.props.StringProperty(options=set())
    fieldOfView: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=0.5)
    farClip: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=10)
    nearClip: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=10)
    clip2: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=10)
    focalDepth: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=2)
    falloffStart: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=1)
    falloffEnd: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=2)
    depthOfField: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=0.5)


class M3Boundings(bpy.types.PropertyGroup):
    radius: bpy.props.FloatProperty(options=set(), default=2)
    center: bpy.props.FloatVectorProperty(options=set(), default=(0, 0, 0), size=3, subtype="XYZ")
    size: bpy.props.FloatVectorProperty(options=set(), default=(0, 0, 0), size=3, subtype="XYZ")


class M3ParticleSpawnPoint(bpy.types.PropertyGroup):
    location: bpy.props.FloatVectorProperty(default=(1, 1, 1), size=3, subtype="XYZ", options={"ANIMATABLE"}, description="The first two values are the initial and final size of particles")


class M3ParticleSystemCopy(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), update=handleParticleSystemCopyNameChange)
    boneName: bpy.props.StringProperty(options=set())
    emissionRate: bpy.props.FloatProperty(default=10, options={"ANIMATABLE"})
    partEmit: bpy.props.IntProperty(default=0, subtype="UNSIGNED", options={"ANIMATABLE"})


class M3ParticleSystem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), update=handleParticleSystemNameChange)
    boneName: bpy.props.StringProperty(options=set())
    bl_update: bpy.props.BoolProperty(options=set(), default=True)
    materialName: bpy.props.StringProperty(options=set(), )
    maxParticles: bpy.props.IntProperty(options=set(), default=20, min=0, subtype="UNSIGNED")
    emissionSpeed1: bpy.props.FloatProperty(options={"ANIMATABLE"}, default=0, description="The initial speed of the particles at emission")
    emissionSpeed2: bpy.props.FloatProperty(default=1, options={"ANIMATABLE"}, description="If emission speed randomization is enabled this value specfies the other end of the range of random speeds")
    randomizeWithEmissionSpeed2: bpy.props.BoolProperty(options=set(), default=False, description="Specifies if the second emission speed value should be used to generate random emission speeds")
    emissionAngleX: bpy.props.FloatProperty(default=0, subtype="ANGLE", options={"ANIMATABLE"}, description="Specifies the X rotation of the emission vector")
    emissionAngleY: bpy.props.FloatProperty(default=0, subtype="ANGLE", options={"ANIMATABLE"}, description="Specifies the Y rotation of the emission vector")
    emissionSpreadX: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"}, description="Specifies in radian by how much the emission vector can be randomly rotated around the X axis")
    emissionSpreadY: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"}, description="Specifies in radian by how much the emission vector can be randomly rotated around the Y axis")
    lifespan1: bpy.props.FloatProperty(default=0.5, min=0, options={"ANIMATABLE"}, description="Specfies how long it takes before the particles start to decay")
    lifespan2: bpy.props.FloatProperty(default=5, min=0, options={"ANIMATABLE"}, description="If random lifespans are enabled this specifies the other end of the range for random lifespan values")
    randomizeWithLifespan2: bpy.props.BoolProperty(options=set(), default=True, description="Specifies if particles should have random lifespans")
    killSphere: bpy.props.FloatProperty(options=set(), default=0, min=0, description="For non-zero values, any particle which goes outside the specified radius from the system is destroyed")
    zAcceleration: bpy.props.FloatProperty(options=set(), default=0, description="Negative gravity which does not get influenced by the emission vector")
    sizeAnimationMiddle: bpy.props.FloatProperty(options=set(), default=0.5, min=0, max=1, subtype="FACTOR", description="Factor of lifetime when the scale animation reaches its middle value")
    colorAnimationMiddle: bpy.props.FloatProperty(options=set(), default=0.5, min=0, max=1, subtype="FACTOR", description="Factor of lifetime when the color animation reaches its middle value")
    alphaAnimationMiddle: bpy.props.FloatProperty(options=set(), default=0.5, min=0, max=1, subtype="FACTOR", description="Factor of lifetime when the alpha animation reaches its middle value")
    rotationAnimationMiddle: bpy.props.FloatProperty(options=set(), default=0.5, min=0, max=1, subtype="FACTOR", description="Factor of lifetime when the scale animation reaches its middle value")
    sizeHoldTime: bpy.props.FloatProperty(options=set(), default=0.3, min=0, max=1, subtype="FACTOR", description="Factor of particle liftime to hold the middle size value")
    colorHoldTime: bpy.props.FloatProperty(options=set(), default=0.3, min=0, max=1, subtype="FACTOR", description="Factor of particle lifetime to hold the middle color value")
    alphaHoldTime: bpy.props.FloatProperty(options=set(), default=0.3, min=0, max=1, subtype="FACTOR", description="Factor of particle lifetime to hold the middle alpha value")
    rotationHoldTime: bpy.props.FloatProperty(options=set(), default=0.3, min=0, max=1, subtype="FACTOR", description="Factor of particle lifetime to hold the middle rotation value")
    sizeSmoothingType: bpy.props.EnumProperty(options=set(), default="0", items=animationSmoothTypeList, description="Determines the shape of the size curve based on the intial, middle , final and hold time value")
    colorSmoothingType: bpy.props.EnumProperty(options=set(), default="0", items=animationSmoothTypeList, description="Determines the shape of the color curve based on the intial, middle , final and hold time value")
    rotationSmoothingType: bpy.props.EnumProperty(options=set(), default="0", items=animationSmoothTypeList, description="Determines the shape of the rotation curve based on the intial, middle , final and hold time value")
    particleSizes1: bpy.props.FloatVectorProperty(default=(1, 1, 1), size=3, subtype="XYZ", options={"ANIMATABLE"}, description="The first two values are the initial and final size of particles")
    rotationValues1: bpy.props.FloatVectorProperty(default=(0, 0, 0), size=3, subtype="XYZ", options={"ANIMATABLE"}, description="The first value is the inital rotation and the second value is the rotation speed")
    initialColor1: bpy.props.FloatVectorProperty(default=(1, 1, 1, 1), min=0, max=1, size=4, subtype="COLOR", options={"ANIMATABLE"}, description="Color of the particle when it gets emitted")
    middleColor1: bpy.props.FloatVectorProperty(default=(1, 1, 1, 1), min=0, max=1, size=4, subtype="COLOR", options={"ANIMATABLE"})
    finalColor1: bpy.props.FloatVectorProperty(default=(1, 1, 1, 0.5), min=0, max=1, size=4, subtype="COLOR", options={"ANIMATABLE"}, description="The color the particle will have when it vanishes")
    drag: bpy.props.FloatProperty(options=set(), default=1, min=0, description="The amounth of speed reduction while the particle is falling, multiplied by the particle's velocity")
    mass: bpy.props.FloatProperty(options=set(), default=0.001, description="Mass determines the effects of drag and the influence of Forces")
    mass2: bpy.props.FloatProperty(options=set(), default=1, description="Mass determines the effects of drag and the influence of Forces")
    randomizeWithMass2: bpy.props.BoolProperty(options=set(), default=True, description="Specifies if the second mass value should be used to generate random mass values")
    unknownFloat2c: bpy.props.FloatProperty(options=set(), default=2)
    trailingEnabled: bpy.props.BoolProperty(options=set(), default=True, description="If trailing is enabled then particles don't follow the particle emitter")
    emissionRate: bpy.props.FloatProperty(default=10, min=0, options={"ANIMATABLE"})
    emissionAreaType: bpy.props.EnumProperty(options=set(), default="2", items=emissionAreaTypeList)
    cutoutEmissionArea: bpy.props.BoolProperty(options=set())
    emissionAreaSize: bpy.props.FloatVectorProperty(default=(0.1, 0.1, 0.1), update=handleParticleSystemAreaSizeChange, size=3, subtype="XYZ", options={"ANIMATABLE"})
    emissionAreaCutoutSize: bpy.props.FloatVectorProperty(default=(0, 0, 0), size=3, subtype="XYZ", options={"ANIMATABLE"})
    emissionAreaRadius: bpy.props.FloatProperty(default=2, update=handleParticleSystemAreaSizeChange, options={"ANIMATABLE"})
    emissionAreaCutoutRadius: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    spawnPoints: bpy.props.CollectionProperty(options=set(), type=M3ParticleSpawnPoint)
    emissionType: bpy.props.EnumProperty(options=set(), default="0", items=particleEmissionTypeList)
    randomizeWithParticleSizes2: bpy.props.BoolProperty(options=set(), default=False, description="Specifies if particles have random sizes")
    particleSizes2: bpy.props.FloatVectorProperty(default=(1, 1, 1), size=3, subtype="XYZ", options={"ANIMATABLE"}, description="The first two values are used to determine a random initial and final size for a particle")
    randomizeWithRotationValues2: bpy.props.BoolProperty(options=set(), default=False)
    rotationValues2: bpy.props.FloatVectorProperty(default=(0, 0, 0), size=3, subtype="XYZ", options={"ANIMATABLE"})
    randomizeWithColor2: bpy.props.BoolProperty(options=set(), default=False)
    initialColor2: bpy.props.FloatVectorProperty(default=(1, 1, 1, 1), min=0, max=1, size=4, subtype="COLOR", options={"ANIMATABLE"})
    middleColor2: bpy.props.FloatVectorProperty(default=(1, 1, 1, 1), min=0, max=1, size=4, subtype="COLOR", options={"ANIMATABLE"})
    finalColor2: bpy.props.FloatVectorProperty(default=(1, 1, 1, 0), min=0, max=1, size=4, subtype="COLOR", options={"ANIMATABLE"})
    partEmit: bpy.props.IntProperty(default=0, min=0, options={"ANIMATABLE"})
    phase1StartImageIndex: bpy.props.IntProperty(options=set(), default=0, min=0, max=255, subtype="UNSIGNED", description="Specifies the cell index shown at start of phase 1 when the image got divided into rows and collumns")
    phase1EndImageIndex: bpy.props.IntProperty(options=set(), default=0, min=0, max=255, subtype="UNSIGNED", description="Specifies the cell index shown at end of phase 1 when the image got divided into rows and collumns")
    phase2StartImageIndex: bpy.props.IntProperty(options=set(), default=0, min=0, max=255, subtype="UNSIGNED", description="Specifies the cell index shown at start of phase 2 when the image got divided into rows and collumns")
    phase2EndImageIndex: bpy.props.IntProperty(options=set(), default=0, min=0, max=255, subtype="UNSIGNED", description="Specifies the cell index shown at end of phase 2 when the image got divided into rows and collumns")
    relativePhase1Length: bpy.props.FloatProperty(options=set(), default=1, min=0, max=1, subtype="FACTOR", name="relative phase 1 length", description="A value of 0.4 means that 40% of the lifetime of the particle the phase 1 image animation will play")
    numberOfColumns: bpy.props.IntProperty(options=set(), default=0, min=0, subtype="UNSIGNED", description="Specifies in how many columns the image gets divided")
    numberOfRows: bpy.props.IntProperty(options=set(), default=0, min=0, subtype="UNSIGNED", description="Specifies in how many rows the image gets divided")
    columnWidth: bpy.props.FloatProperty(options=set(), default=float("inf"), min=0, max=1, subtype="FACTOR", description="Specifies the width of one column, relative to an image with width 1")
    rowHeight: bpy.props.FloatProperty(options=set(), default=float("inf"), min=0, max=1, subtype="FACTOR", description="Specifies the height of one row, relative to an image with height 1")
    bounce: bpy.props.FloatProperty(options=set(), default=0, subtype="FACTOR", min=0, max=1, description="Specifies the amount of velocity preserved when recoiling from a collision. 1 is elastic and 0 is sticky.")
    friction: bpy.props.FloatProperty(options=set(), default=1, subtype="FACTOR", min=0, max=1, description="Specifies the amount of velocity preserved when striking a collision surface. 1 is slippery and 0 is stuck.")
    unknownFloat6: bpy.props.FloatProperty(options=set(), default=1)
    unknownFloat7: bpy.props.FloatProperty(options=set(), default=1)
    particleType: bpy.props.EnumProperty(options=set(), default="0", items=particleTypeList)
    lengthWidthRatio: bpy.props.FloatProperty(options=set(), default=1)
    localForceChannels: bpy.props.BoolVectorProperty(options=set(), default=tuple(16 * [False]), size=16, subtype="LAYER", description="If a model internal force shares a local force channel with a particle system then it affects it")
    worldForceChannels: bpy.props.BoolVectorProperty(options=set(), default=tuple(16 * [False]), size=16, subtype="LAYER", description="If a force shares a force channel with a particle system then it affects it")
    copies: bpy.props.CollectionProperty(options=set(), type=M3ParticleSystemCopy)
    copyIndex: bpy.props.IntProperty(options=set(), update=handleParticleSystemCopyIndexChanged)
    trailingParticlesName: bpy.props.StringProperty(options=set())
    trailingParticlesChance: bpy.props.FloatProperty(options=set(), default=0, min=0, max=1, subtype="FACTOR", name="trailingParticlesChance")
    trailingParticlesRate: bpy.props.FloatProperty(default=10, name="trail. emiss. rate", options={"ANIMATABLE"})
    noiseAmplitude: bpy.props.FloatProperty(options=set(), default=0)
    noiseFrequency: bpy.props.FloatProperty(options=set(), default=0)
    noiseCohesion: bpy.props.FloatProperty(options=set(), default=0, description="Prevents the particles from spreading to far from noise")
    noiseEdge: bpy.props.FloatProperty(options=set(), default=0, min=0, max=0.5, subtype="FACTOR", description="The closer the value is to 0.5 the less noise will be at the start of particles life time")
    sort: bpy.props.BoolProperty(options=set())
    collideTerrain: bpy.props.BoolProperty(options=set())
    collideObjects: bpy.props.BoolProperty(options=set())
    spawnOnBounce: bpy.props.BoolProperty(options=set())
    inheritEmissionParams: bpy.props.BoolProperty(options=set())
    inheritParentVel: bpy.props.BoolProperty(options=set())
    sortByZHeight: bpy.props.BoolProperty(options=set())
    reverseIteration: bpy.props.BoolProperty(options=set())
    litParts: bpy.props.BoolProperty(options=set())
    randFlipBookStart: bpy.props.BoolProperty(options=set())
    multiplyByGravity: bpy.props.BoolProperty(options=set())
    clampTailParts: bpy.props.BoolProperty(options=set())
    spawnTrailingParts: bpy.props.BoolProperty(options=set())
    fixLengthTailParts: bpy.props.BoolProperty(options=set())
    useVertexAlpha: bpy.props.BoolProperty(options=set())
    modelParts: bpy.props.BoolProperty(options=set())
    swapYZonModelParts: bpy.props.BoolProperty(options=set())
    scaleTimeByParent: bpy.props.BoolProperty(options=set())
    useLocalTime: bpy.props.BoolProperty(options=set())
    simulateOnInit: bpy.props.BoolProperty(options=set())
    copy: bpy.props.BoolProperty(options=set())
    windMultiplier: bpy.props.FloatProperty(options=set(), default=0, name="windMultiplier")
    lodReduce: bpy.props.EnumProperty(options=set(), default="0", items=shared.lodEnum)
    lodCut: bpy.props.EnumProperty(options=set(), default="0", items=shared.lodEnum)


class M3RibbonEndPoint(bpy.types.PropertyGroup):
    # name is also bone name
    name: bpy.props.StringProperty(options=set())
    tangent1: bpy.props.FloatProperty(options=set())
    tangent2: bpy.props.FloatProperty(options=set())
    tangent3: bpy.props.FloatProperty(options=set())
    yaw: bpy.props.FloatProperty(subtype="ANGLE")
    pitch: bpy.props.FloatProperty(subtype="ANGLE")
    length: bpy.props.FloatProperty(default=1)
    yawVariationType: bpy.props.EnumProperty(options=set(), items=ribbonCurveType)
    yawVariationAmplitude: bpy.props.FloatProperty(default=0)
    yawVariationFrequency: bpy.props.FloatProperty(default=0)
    pitchVariationType: bpy.props.EnumProperty(options=set(), items=ribbonCurveType)
    pitchVariationAmplitude: bpy.props.FloatProperty(default=0)
    pitchVariationFrequency: bpy.props.FloatProperty(default=0)
    speedVariationType: bpy.props.EnumProperty(options=set(), items=ribbonCurveType)
    speedVariationAmplitude: bpy.props.FloatProperty(default=0)
    speedVariationFrequency: bpy.props.FloatProperty(default=0)


class M3Ribbon(bpy.types.PropertyGroup):
    bl_update: bpy.props.BoolProperty(options=set(), default=True)
    name: bpy.props.StringProperty(options=set(), update=handleRibbonNameChange)
    boneName: bpy.props.StringProperty(options=set())
    materialName: bpy.props.StringProperty(options=set())
    speed: bpy.props.FloatProperty(default=1, options={"ANIMATABLE"})
    size: bpy.props.FloatVectorProperty(default=(1, 1, 1), size=3, subtype="XYZ", options={"ANIMATABLE"})
    rotation: bpy.props.FloatVectorProperty(default=(1, 1, 1), size=3, subtype="XYZ", options={"ANIMATABLE"})
    baseColoring: bpy.props.FloatVectorProperty(size=4, subtype="COLOR", min=0, max=1, options={"ANIMATABLE"})
    centerColoring: bpy.props.FloatVectorProperty(size=4, subtype="COLOR", min=0, max=1, options={"ANIMATABLE"})
    tipColoring: bpy.props.FloatVectorProperty(size=4, subtype="COLOR", min=0, max=1, options={"ANIMATABLE"})
    sizeMiddleTime: bpy.props.FloatProperty(options=set(), default=1.0, min=0, max=1, subtype="FACTOR")
    colorMiddleTime: bpy.props.FloatProperty(options=set(), default=1.0, min=0, max=1, subtype="FACTOR")
    alphaMiddleTime: bpy.props.FloatProperty(options=set(), default=1.0, min=0, max=1, subtype="FACTOR")
    rotationMiddleTime: bpy.props.FloatProperty(options=set(), default=1.0, min=0, max=1, subtype="FACTOR")
    sizeMiddleHoldTime: bpy.props.FloatProperty(options=set(), min=0, max=1)
    colorMiddleHoldTime: bpy.props.FloatProperty(options=set(), min=0, max=1)
    alphaMiddleHoldTime: bpy.props.FloatProperty(options=set(), min=0, max=1)
    rotationMiddleHoldTime: bpy.props.FloatProperty(options=set(), min=0, max=1)
    sizeSmoothing: bpy.props.EnumProperty(options=set(), default="0", items=animationSmoothTypeList, description="Determines the shape of the size curve based on the intial, middle , final and hold time value")
    colorSmoothing: bpy.props.EnumProperty(options=set(), default="0", items=animationSmoothTypeList, description="Determines the shape of the color curve based on the intial, middle , final and hold time value")
    gravity: bpy.props.FloatProperty(options=set())
    drag: bpy.props.FloatProperty(options=set(), default=1)
    bounce: bpy.props.FloatProperty(options=set(), min=0, max=1, subtype="FACTOR")
    friction: bpy.props.FloatProperty(options=set(), min=0, max=1, subtype="FACTOR")
    mass: bpy.props.FloatProperty(options=set())
    surfaceNoiseAmplitude: bpy.props.FloatProperty(options=set(), default=0)
    surfaceNoiseNumberOfWaves: bpy.props.FloatProperty(options=set(), default=0)
    surfaceNoiseFrequency: bpy.props.FloatProperty(options=set(), default=0)
    surfaceNoiseScale: bpy.props.FloatProperty(options=set(), default=0.2)
    ribbonType: bpy.props.EnumProperty(options=set(), default="0", items=ribbonTypeList)
    ribbonDivisions: bpy.props.FloatProperty(options=set(), default=20)
    ribbonSides: bpy.props.IntProperty(options=set(), default=5, subtype="UNSIGNED")
    length: bpy.props.FloatProperty(default=1, options={"ANIMATABLE"})
    yawVariationType: bpy.props.EnumProperty(options=set(), items=ribbonCurveType)
    yawVariationAmplitude: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    yawVariationFrequency: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    pitchVariationType: bpy.props.EnumProperty(options=set(), items=ribbonCurveType)
    pitchVariationAmplitude: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    pitchVariationFrequency: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    speedVariationType: bpy.props.EnumProperty(options=set(), items=ribbonCurveType)
    speedVariationAmplitude: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    speedVariationFrequency: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    sizeVariationType: bpy.props.EnumProperty(options=set(), items=ribbonCurveType)
    sizeVariationAmplitude: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    sizeVariationFrequency: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    alphaVariationType: bpy.props.EnumProperty(options=set(), items=ribbonCurveType)
    alphaVariationAmplitude: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    alphaVariationFrequency: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    parentVelocity: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    overlayPhase: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    active: bpy.props.BoolProperty(default=True)
    localForceChannels: bpy.props.BoolVectorProperty(options=set(), default=tuple(16 * [False]), size=16, subtype="LAYER", description="If a model internal force shares a local force channel with a ribbon then it affects it")
    worldForceChannels: bpy.props.BoolVectorProperty(options=set(), default=tuple(16 * [False]), size=16, subtype="LAYER", description="If a force shares a force channel with a ribbon then it affects it")
    collideWithTerrain: bpy.props.BoolProperty(options=set(), default=False)
    collideWithObjects: bpy.props.BoolProperty(options=set(), default=False)
    edgeFalloff: bpy.props.BoolProperty(options=set(), default=False)
    inheritParentVelocity: bpy.props.BoolProperty(default=False)
    smoothSize: bpy.props.BoolProperty(options=set(), default=False)
    bezierSmoothSize: bpy.props.BoolProperty(options=set(), default=False)
    useVertexAlpha: bpy.props.BoolProperty(options=set(), default=False)
    scaleTimeByParent: bpy.props.BoolProperty(options=set(), default=False)
    forceCPUSimulation: bpy.props.BoolProperty(options=set(), default=False)
    useLocaleTime: bpy.props.BoolProperty(options=set(), default=False)
    simulateOnInitialization: bpy.props.BoolProperty(options=set(), default=False)
    useLengthAndTime: bpy.props.BoolProperty(options=set(), default=False)
    accurateGPUTangents: bpy.props.BoolProperty(options=set(), default=False)
    worldSpace: bpy.props.BoolProperty(options=set())
    endPoints: bpy.props.CollectionProperty(options=set(), type=M3RibbonEndPoint)
    endPointIndex: bpy.props.IntProperty(options=set(), default=-1, update=handleRibbonEndPointIndexChanged)
    lodReduce: bpy.props.EnumProperty(options=set(), default="0", items=shared.lodEnum)
    lodCut: bpy.props.EnumProperty(options=set(), default="0", items=shared.lodEnum)
    yaw: bpy.props.FloatProperty(default=0, subtype="ANGLE", options={"ANIMATABLE"})
    pitch: bpy.props.FloatProperty(default=0, subtype="ANGLE", options={"ANIMATABLE"})
    cullType: bpy.props.EnumProperty(options=set(), default="0", items=ribbonCullType)
    lifespan: bpy.props.FloatProperty(default=0.5)
    starRatio: bpy.props.FloatProperty(options=set(), default=0.5, min=0, max=1, subtype="FACTOR")


class M3Force(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), update=handleForceNameOrTypeChange)
    boneName: bpy.props.StringProperty(options=set())
    bl_update: bpy.props.BoolProperty(options=set(), default=True)
    type: bpy.props.EnumProperty(options=set(), default="0", items=forceTypeList, update=handleForceNameOrTypeChange)
    shape: bpy.props.EnumProperty(options=set(), default="0", items=forceShapeList, update=handleForceShapeUpdate)
    channels: bpy.props.BoolVectorProperty(options=set(), default=tuple(32 * [False]), size=32, subtype="LAYER", description="If a force shares a force channel with a particle system then it affects it")
    strength: bpy.props.FloatProperty(default=1, options={"ANIMATABLE"})
    width: bpy.props.FloatProperty(default=1, update=handleForceShapeUpdate, options={"ANIMATABLE"}, min=0.001)
    height: bpy.props.FloatProperty(default=0.05, update=handleForceShapeUpdate, options={"ANIMATABLE"}, min=0.001, description="Value should be in the 0.001-0.999 range when force type is Cone Dome")
    length: bpy.props.FloatProperty(default=0.05, update=handleForceShapeUpdate, options={"ANIMATABLE"}, min=0.001)
    useFalloff: bpy.props.BoolProperty(options=set())
    useHeightGradient: bpy.props.BoolProperty(options=set())
    unbounded: bpy.props.BoolProperty(options=set())


class M3PhysicsShape(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set())
    offset: bpy.props.FloatVectorProperty(options=set(), default=(0, 0, 0), size=3, subtype="XYZ", update=handlePhysicsShapeUpdate)
    rotationEuler: bpy.props.FloatVectorProperty(options=set(), default=(0, 0, 0), size=3, subtype="EULER", unit="ROTATION", update=handlePhysicsShapeUpdate)
    scale: bpy.props.FloatVectorProperty(options=set(), default=(1, 1, 1), size=3, subtype="XYZ", update=handlePhysicsShapeUpdate)
    shape: bpy.props.EnumProperty(options=set(), default="0", items=physicsShapeTypeList, update=handlePhysicsShapeUpdate)
    meshObjectName: bpy.props.StringProperty(options=set())
    # TODO: convex hull properties...
    size0: bpy.props.FloatProperty(options=set(), default=1, update=handlePhysicsShapeUpdate)
    size1: bpy.props.FloatProperty(options=set(), default=1, update=handlePhysicsShapeUpdate)
    size2: bpy.props.FloatProperty(options=set(), default=1, update=handlePhysicsShapeUpdate)


class M3RigidBody(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), update=handleRigidBodyBoneChange)
    nameOld: bpy.props.StringProperty(options=set())
    unknownAt0: bpy.props.FloatProperty(options=set(), default=5)
    unknownAt4: bpy.props.FloatProperty(options=set(), default=4)
    unknownAt8: bpy.props.FloatProperty(options=set(), default=0.8)
    # skip other unknown values for now
    simulationType: bpy.props.IntProperty(options=set(), default=1)
    physicalMaterial: bpy.props.IntProperty(options=set(), default=0)
    density: bpy.props.FloatProperty(options=set(), default=2400)
    friction: bpy.props.FloatProperty(options=set(), default=0.7, subtype="FACTOR", min=0, max=1)
    restitution: bpy.props.FloatProperty(options=set(), default=0.1)
    linearDamp: bpy.props.FloatProperty(options=set(), default=0.001)
    angularDamp: bpy.props.FloatProperty(options=set(), default=0.001)
    gravityScale: bpy.props.FloatProperty(options=set(), default=1)
    physicsShapes: bpy.props.CollectionProperty(options=set(), type=M3PhysicsShape)
    physicsShapeIndex: bpy.props.IntProperty(options=set())
    collidable: bpy.props.BoolProperty(options=set(), default=True)
    walkable: bpy.props.BoolProperty(options=set(), default=False)
    stackable: bpy.props.BoolProperty(options=set(), default=False)
    simulateOnCollision: bpy.props.BoolProperty(options=set(), default=False)
    ignoreLocalBodies: bpy.props.BoolProperty(options=set(), default=False)
    alwaysExists: bpy.props.BoolProperty(options=set(), default=False)
    doNotSimulate: bpy.props.BoolProperty(options=set(), default=False)
    localForces: bpy.props.BoolVectorProperty(options=set(), default=tuple(16 * [False]), size=16, subtype="LAYER")
    wind: bpy.props.BoolProperty(options=set(), default=False)
    explosion: bpy.props.BoolProperty(options=set(), default=False)
    energy: bpy.props.BoolProperty(options=set(), default=False)
    blood: bpy.props.BoolProperty(options=set(), default=False)
    magnetic: bpy.props.BoolProperty(options=set(), default=False)
    grass: bpy.props.BoolProperty(options=set(), default=False)
    brush: bpy.props.BoolProperty(options=set(), default=False)
    trees: bpy.props.BoolProperty(options=set(), default=False)
    priority: bpy.props.IntProperty(options=set(), default=0)


class M3AttachmentPoint(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), update=handleAttachmentPointNameOrTypeChange)
    boneName: bpy.props.StringProperty(options=set())
    bl_update: bpy.props.BoolProperty(options=set(), default=True)
    volumeType: bpy.props.EnumProperty(options=set(), default="-1", update=handleAttachmentVolumeTypeChange, items=attachmentVolumeTypeList)
    volumeSize0: bpy.props.FloatProperty(options=set(), default=1, update=handleAttachmentVolumeSizeChange)
    volumeSize1: bpy.props.FloatProperty(options=set(), default=0, update=handleAttachmentVolumeSizeChange)
    volumeSize2: bpy.props.FloatProperty(options=set(), default=0, update=handleAttachmentVolumeSizeChange)


class M3SimpleGeometricShape(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set())
    boneName: bpy.props.StringProperty(options=set(), update=handleGeometricShapeTypeOrBoneNameUpdate)
    shape: bpy.props.EnumProperty(options=set(), default="1", items=geometricShapeTypeList, update=handleGeometricShapeTypeOrBoneNameUpdate)
    size0: bpy.props.FloatProperty(options=set(), default=1, update=handleGeometricShapeUpdate)
    size1: bpy.props.FloatProperty(options=set(), default=0, update=handleGeometricShapeUpdate)
    size2: bpy.props.FloatProperty(options=set(), default=0, update=handleGeometricShapeUpdate)
    offset: bpy.props.FloatVectorProperty(options=set(), default=(0, 0, 0), size=3, subtype="XYZ", update=handleGeometricShapeUpdate)
    rotationEuler: bpy.props.FloatVectorProperty(options=set(), default=(0, 0, 0), size=3, subtype="EULER", unit="ROTATION", update=handleGeometricShapeUpdate)
    scale: bpy.props.FloatVectorProperty(options=set(), default=(1, 1, 1), size=3, subtype="XYZ", update=handleGeometricShapeUpdate)


class M3BoneVisiblityOptions(bpy.types.PropertyGroup):
    showFuzzyHitTests: bpy.props.BoolProperty(options=set(), default=True, update=handleFuzzyHitTestVisiblityUpdate)
    showTightHitTest: bpy.props.BoolProperty(options=set(), default=True, update=handleTightHitTestVisiblityUpdate)
    showAttachmentPoints: bpy.props.BoolProperty(options=set(), default=True, update=handleAttachmentPointVisibilityUpdate)
    showParticleSystems: bpy.props.BoolProperty(options=set(), default=True, update=handleParticleSystemsVisiblityUpdate)
    showRibbons: bpy.props.BoolProperty(options=set(), default=True, update=handleRibbonsVisiblityUpdate)
    showLights: bpy.props.BoolProperty(options=set(), default=True, update=handleLightsVisiblityUpdate)
    showForces: bpy.props.BoolProperty(options=set(), default=True, update=handleForcesVisiblityUpdate)
    showCameras: bpy.props.BoolProperty(options=set(), default=True, update=handleCamerasVisiblityUpdate)
    showPhysicsShapes: bpy.props.BoolProperty(options=set(), default=True, update=handlePhysicsShapeVisibilityUpdate)
    showProjections: bpy.props.BoolProperty(options=set(), default=True, update=handleProjectionVisibilityUpdate)
    showWarps: bpy.props.BoolProperty(options=set(), default=True, update=handleWarpVisibilityUpdate)


class M3Warp(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), update=handleWarpNameChange)
    boneName: bpy.props.StringProperty(options=set())
    bl_update: bpy.props.BoolProperty(options=set())
    materialName: bpy.props.StringProperty(options=set())
    radius: bpy.props.FloatProperty(default=1, min=0, update=handleWarpRadiusChange, options={"ANIMATABLE"})
    unknown9306aac0: bpy.props.FloatProperty(default=10, options={"ANIMATABLE"})
    compressionStrength: bpy.props.FloatProperty(default=1, options={"ANIMATABLE"})
    unknown50c7f2b4: bpy.props.FloatProperty(default=1, options={"ANIMATABLE"})
    unknown8d9c977c: bpy.props.FloatProperty(default=1, options={"ANIMATABLE"})
    unknownca6025a2: bpy.props.FloatProperty(default=1, options={"ANIMATABLE"})


class M3Light(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set(), default="", update=handleLightNameOrTypeChange)
    boneName: bpy.props.StringProperty(options=set())
    bl_update: bpy.props.BoolProperty(options=set(), default=True)
    lightType: bpy.props.EnumProperty(options=set(), default="1", items=lightTypeList, update=handleLightNameOrTypeChange)
    lightColor: bpy.props.FloatVectorProperty(default=(1, 1, 1), min=0, max=1, size=3, subtype="COLOR", options={"ANIMATABLE"})
    lightIntensity: bpy.props.FloatProperty(default=1, options={"ANIMATABLE"})
    specColor: bpy.props.FloatVectorProperty(default=(1, 1, 1), min=0, max=1, size=3, subtype="COLOR", options={"ANIMATABLE"})
    specIntensity: bpy.props.FloatProperty(default=0, options={"ANIMATABLE"})
    attenuationNear: bpy.props.FloatProperty(default=2.5, options={"ANIMATABLE"})
    unknownAt148: bpy.props.FloatProperty(options=set(), default=2.5)
    attenuationFar: bpy.props.FloatProperty(default=3, update=handleLightSizeChange, options={"ANIMATABLE"})
    hotSpot: bpy.props.FloatProperty(default=1, options={"ANIMATABLE"})
    falloff: bpy.props.FloatProperty(default=1, update=handleLightSizeChange, options={"ANIMATABLE"})
    lodCut: bpy.props.EnumProperty(options=set(), default="0", items=shared.lodEnum)
    shadowLodCut: bpy.props.EnumProperty(options=set(), default="0", items=shared.lodEnum)
    shadowCast: bpy.props.BoolProperty(options=set())
    specular: bpy.props.BoolProperty(options=set())
    affectedByAO: bpy.props.BoolProperty(options=set())
    lightOpaqueObjects: bpy.props.BoolProperty(options=set(), default=True)
    lightTransparentObjects: bpy.props.BoolProperty(options=set(), default=False)
    useTeamColor: bpy.props.BoolProperty(options=set())


class M3BillboardBehavior(bpy.types.PropertyGroup):
    # name is also bone name
    name: bpy.props.StringProperty(options=set(), default="")
    billboardType: bpy.props.EnumProperty(options=set(), default="6", items=billboardBehaviorTypeList)


class M3InverseKinematicChain(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set())
    boneName1: bpy.props.StringProperty(options=set())
    boneName2: bpy.props.StringProperty(options=set())
    maxSearchUp: bpy.props.FloatProperty(options=set())
    maxSearchDown: bpy.props.FloatProperty(options=set())
    maxSpeed: bpy.props.FloatProperty(options=set(), min=0)
    goalPosThreshold: bpy.props.FloatProperty(options=set(), min=0)


class M3TurretBehaviorPart(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set())
    forwardX: bpy.props.FloatVectorProperty(options=set(), size=4, default=(0, -1, 0, 0))
    forwardY: bpy.props.FloatVectorProperty(options=set(), size=4, default=(1, 0, 0, 0))
    forwardZ: bpy.props.FloatVectorProperty(options=set(), size=4, default=(0, 0, 1, 0))
    upX: bpy.props.FloatVectorProperty(options=set(), size=4, default=(0, 0, 0, 1))
    upY: bpy.props.FloatVectorProperty(options=set(), size=4, default=(0, 0, 0, 1))
    upZ: bpy.props.FloatVectorProperty(options=set(), size=4, default=(0, 0, 0, 1))
    mainTurretBone: bpy.props.BoolProperty(options=set())
    groupId: bpy.props.IntProperty(options=set(), subtype="UNSIGNED", default=1)
    yawWeight: bpy.props.FloatProperty(options=set(), min=0, max=1, default=1, subtype="FACTOR")
    yawLimited: bpy.props.BoolProperty(options=set())
    yawMin: bpy.props.FloatProperty(options=set(), subtype="ANGLE")
    yawMax: bpy.props.FloatProperty(options=set(), subtype="ANGLE")
    pitchWeight: bpy.props.FloatProperty(options=set(), min=0, max=1, default=1, subtype="FACTOR")
    pitchLimited: bpy.props.BoolProperty(options=set())
    pitchMin: bpy.props.FloatProperty(options=set(), subtype="ANGLE")
    pitchMax: bpy.props.FloatProperty(options=set(), subtype="ANGLE")
    unknownAt132: bpy.props.FloatProperty(options=set())
    unknownAt136: bpy.props.FloatProperty(options=set())
    unknownAt140: bpy.props.FloatProperty(options=set())
    unknownAt144: bpy.props.FloatProperty(options=set())
    unknownAt148: bpy.props.FloatProperty(options=set())


class M3TurretBehavior(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(options=set())
    parts: bpy.props.CollectionProperty(type=M3TurretBehaviorPart)
    part_index: bpy.props.IntProperty(default=-1, update=handleTurretBehaviorPartIndexChanged)


class M3PhysicsJoint(bpy.types.PropertyGroup):
    bl_update: bpy.props.BoolProperty(options=set(), default=True)
    name: bpy.props.StringProperty(options=set())
    boneName1: bpy.props.StringProperty(options=set())
    boneName2: bpy.props.StringProperty(options=set())
    jointType: bpy.props.EnumProperty(options=set(), items=physicsJointType)
    offset1: bpy.props.FloatVectorProperty(options=set(), size=3, subtype="XYZ", update=handlePhysicsJointPivotDisplay)
    rotation1: bpy.props.FloatVectorProperty(options=set(), size=3, subtype="EULER", unit="ROTATION", update=handlePhysicsJointPivotDisplay)
    offset2: bpy.props.FloatVectorProperty(options=set(), size=3, subtype="XYZ", update=handlePhysicsJointPivotDisplay)
    rotation2: bpy.props.FloatVectorProperty(options=set(), size=3, subtype="EULER", unit="ROTATION", update=handlePhysicsJointPivotDisplay)
    limit: bpy.props.BoolProperty(options=set())
    limitMin: bpy.props.FloatProperty(options=set())
    limitMax: bpy.props.FloatProperty(options=set())
    coneAngle: bpy.props.FloatProperty(options=set())
    friction: bpy.props.BoolProperty(options=set())
    frictionAmount: bpy.props.FloatProperty(options=set(), default=0.2)
    dampingRatio: bpy.props.FloatProperty(options=set(), default=0.7, min=0, max=1, subtype="FACTOR")
    angularFrequency: bpy.props.FloatProperty(options=set(), default=5)
    shapeCollisionValue: bpy.props.IntProperty(options=set())


class BoneVisibilityPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_bone_visibility"
    bl_label = "M3 Bone Visibility"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.prop(scene.m3_bone_visiblity_options, "showFuzzyHitTests", text="Fuzzy Hit Tests")
        layout.prop(scene.m3_bone_visiblity_options, "showTightHitTest", text="Tight Hit Test")
        layout.prop(scene.m3_bone_visiblity_options, "showAttachmentPoints", text="Attachment Points")
        layout.prop(scene.m3_bone_visiblity_options, "showParticleSystems", text="Particle Systems")
        layout.prop(scene.m3_bone_visiblity_options, "showRibbons", text="Ribbons")
        layout.prop(scene.m3_bone_visiblity_options, "showLights", text="Lights")
        layout.prop(scene.m3_bone_visiblity_options, "showForces", text="Forces")
        layout.prop(scene.m3_bone_visiblity_options, "showCameras", text="Cameras")
        layout.prop(scene.m3_bone_visiblity_options, "showPhysicsShapes", text="Physics Shapes")
        layout.prop(scene.m3_bone_visiblity_options, "showProjections", text="Projections")
        layout.prop(scene.m3_bone_visiblity_options, "showWarps", text="Warps")


class AnimationSequencesMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_M3_animations"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout
        layout.operator("m3.animations_duplicate", text="Duplicate")


class MaterialReferencesMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_M3_material_references"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout
        layout.operator("m3.materials_duplicate", text="Duplicate")


class CameraMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_M3_cameras"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout
        layout.operator("m3.cameras_duplicate", text="Duplicate")


class ParticleSystemsMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_M3_particle_systems"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout
        layout.operator("m3.particle_systems_duplicate", text="Duplicate")


class RibbonsMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_M3_ribbons"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout
        layout.operator("m3.ribbons_duplicate", text="Duplicate")


class ForceMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_M3_forces"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout
        layout.operator("m3.forces_duplicate", text="Duplicate")


class RigidBodyMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_M3_rigid_bodies"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout
        layout.operator("m3.rigid_bodies_duplicate")


class LightMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_M3_lights"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout
        layout.operator("m3.lights_duplicate", text="Duplicate")


class WarpMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_M3_warps"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout
        layout.operator("m3.warps_duplicate", text="Duplicate")


class AnimationSequencesPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_animations"
    bl_label = "M3 Animation Sequences"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        rows = 2
        if len(scene.m3_animations) > 1:
            rows = 5

        layout.operator("m3.animations_deselect", text="Edit Default Values")
        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_animations", scene, "m3_animations", scene, "m3_animation_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.animations_add", icon="ADD", text="")
        col.operator("m3.animations_remove", icon="REMOVE", text="")
        col.separator()
        col.menu("OBJECT_MT_M3_animations", icon="DOWNARROW_HLT", text="")

        if len(scene.m3_animations) > 1:
            col.separator()
            col.operator("m3.animations_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.animations_move", icon="TRIA_DOWN", text="").shift = 1

        animationIndex = scene.m3_animation_index
        if animationIndex >= 0 and animationIndex < len(scene.m3_animations):
            animation = scene.m3_animations[animationIndex]
            layout.prop(animation, "name", text="Name")


class AnimationSequencesPropPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_animations_prop"
    bl_label = "Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_animations"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_animation_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        animationIndex = scene.m3_animation_index
        if animationIndex >= 0 and animationIndex < len(scene.m3_animations):
            animation = scene.m3_animations[animationIndex]
            row = layout.row()
            col = row.column(align=True)
            col.prop(animation, "startFrame", text="Start Frame")
            col.prop(animation, "exlusiveEndFrame", text="End Frame")
            col = row.column(align=True)
            col.prop(animation, "movementSpeed", text="Mov. Speed")
            col.prop(animation, "frequency", text="Frequency")
            col = layout.column_flow(columns=2)
            col.prop(animation, "notLooping", text="Doesn't Loop")
            col.prop(animation, "alwaysGlobal", text="Always Global")
            col.prop(animation, "globalInPreviewer", text="Global In Previewer")

            if not len(scene.m3_rigid_bodies) > 0:
                return

            row = layout.row()
            row.prop(animation, "useSimulateFrame", text="Use physics")
            sub = row.split()
            sub.active = animation.useSimulateFrame
            sub.prop(animation, "simulateFrame", text="Simulate after frame")


class AnimationSequenceTransformationCollectionsPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_STCs"
    bl_label = "Sub Animations"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_animations"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_animation_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        animation = scene.m3_animations[scene.m3_animation_index]

        rows = 2
        if len(animation.transformationCollections) > 1:
            rows = 4

        row = layout.row()
        col = row.column()

        col.template_list("UI_UL_list", "m3_stcs", animation, "transformationCollections", animation, "transformationCollectionIndex", rows=rows)

        col = row.column(align=True)
        col.operator("m3.stc_add", icon="ADD", text="")
        col.operator("m3.stc_remove", icon="REMOVE", text="")

        if len(animation.transformationCollections) > 1:
            col.separator()
            col.operator("m3.stc_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.stc_move", icon="TRIA_DOWN", text="").shift = 1

        index = animation.transformationCollectionIndex
        if index >= 0 and index < len(animation.transformationCollections):
            transformationCollection = animation.transformationCollections[index]
            layout.separator()
            layout.prop(transformationCollection, "name", text="Name")
            layout.prop(transformationCollection, "runsConcurrent", text="Runs Concurrent")
            layout.prop(transformationCollection, "priority", text="Priority")
            row = layout.row()
            row.operator("m3.stc_select", text="Select FCurves")
            row.operator("m3.stc_assign", text="Assign FCurves")


def displayMaterialName(scene: bt.Scene, layout: bt.UILayout, materialReference: cm.M3Material):
    layout = layout.split()
    material = cm.getMaterial(scene, materialReference.materialType, materialReference.materialIndex)
    if material is not None:
        layout.prop(material, "name", text="Name")
    else:
        layout.label(text=("Name: %s [Unsupported]" % materialReference.name))
    try:
        materialTypeName = shared.materialNames[materialReference.materialType]
    except KeyError:
        materialTypeName = "Unknown [%s]" % materialReference.materialType
    layout.label(text=("Type: %s" % materialTypeName))


class MaterialReferencesPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_material_references"
    bl_label = "M3 Materials"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        rows = 2
        if len(scene.m3_material_references) == 1:
            rows = 3
        elif len(scene.m3_material_references) > 1:
            rows = 5

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_material_references", scene, "m3_material_references", scene, "m3_material_reference_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.materials_add", icon="ADD", text="")
        col.operator("m3.materials_remove", icon="REMOVE", text="")

        if len(scene.m3_material_references) > 0:
            col.separator()
            col.menu("OBJECT_MT_M3_material_references", icon="DOWNARROW_HLT", text="")

        if len(scene.m3_material_references) > 1:
            col.separator()
            col.operator("m3.materials_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.materials_move", icon="TRIA_DOWN", text="").shift = 1

        materialIndex = scene.m3_material_reference_index

        if materialIndex >= 0:
            materialReference = scene.m3_material_references[materialIndex]

            displayMaterialName(scene, layout, materialReference)


class MaterialSelectionPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_material_selection"
    bl_label = "M3 Material Selection"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        o = context.object
        return o and (o.data is not None) and (o.type == "MESH")

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        mesh = context.object.data
        row = layout.row()

        row.prop_search(mesh, "m3_material_name", scene, "m3_material_references", text="M3 Material", icon="NONE")
        row.operator("m3.create_material_for_mesh", icon="ADD", text="")

        materialReference = scene.m3_material_references.get(mesh.m3_material_name)
        if materialReference is not None:
            displayMaterialName(scene, layout, materialReference)


def displayMaterialPropertiesUI(scene: bt.Scene, layout: bt.UILayout, materialReference):
    materialType = materialReference.materialType
    materialIndex = materialReference.materialIndex

    if materialType == shared.standardMaterialTypeIndex:
        material = scene.m3_standard_materials[materialIndex]
        col = layout.column(align=True)
        col.prop(material, "blendMode", text="Blend Mode")
        col.prop(material, "layerBlendType")
        col.prop(material, "emisBlendType", text="Emis. Blend Type")
        col.prop(material, "emisMode", text="Emis. Mode")
        row = layout.row()
        col = row.column(align=True)
        col.prop(material, "specType", text="Spec. Type")
        col.prop(material, "specularity")
        col.prop(material, "specMult")
        col.prop(material, "emisMult")
        col = row.column(align=True)
        col.prop(material, "useDepthBlendFalloff", text="Depth Blend Falloff:")
        sub = col.column()
        sub.active = material.useDepthBlendFalloff
        sub.prop(material, "depthBlendFalloff", text="")
        col.prop(material, "priority")
        col.prop(material, "cutoutThresh", text="Cutout Thresh.", slider=True)

        col = layout.column(align=True)
        col.prop(material, "parallaxHeight")

        col = layout.column(align=True, heading="Environment map multipliers")
        col.prop(material, "envConstMult")
        col.prop(material, "envDiffMult")
        col.prop(material, "envSpecMult")

    elif materialType == shared.displacementMaterialTypeIndex:
        material = scene.m3_displacement_materials[materialIndex]
        col = layout.row(align=True)
        col.prop(material, "strengthFactor", text="Strength Factor")
        col.prop(material, "priority", text="Priority")
    elif materialType == shared.compositeMaterialTypeIndex:
        material = scene.m3_composite_materials[materialIndex]

        rows = 2
        if len(material.sections) > 1:
            rows = 4

        layout.label(text="Sections:")
        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_material_sections", material, "sections", material, "sectionIndex", rows=rows)

        col = row.column(align=True)
        col.operator("m3.composite_material_add_section", icon="ADD", text="")
        col.operator("m3.composite_material_remove_section", icon="REMOVE", text="")

        if len(material.sections) > 1:
            col.separator()
            col.operator("m3.composite_material_move_section", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.composite_material_move_section", icon="TRIA_DOWN", text="").shift = 1

        sectionIndex = material.sectionIndex
        if (sectionIndex >= 0) and (sectionIndex < len(material.sections)):
            section = material.sections[sectionIndex]
            layout.prop_search(section, "name", scene, "m3_material_references", text="Material", icon="NONE")
            layout.prop(section, "alphaFactor", text="Alpha Factor")
    elif materialType == shared.volumeMaterialTypeIndex:
        material = scene.m3_volume_materials[materialIndex]
        layout.prop(material, "volumeDensity", text="Volume Density")
    elif materialType == shared.volumeNoiseMaterialTypeIndex:
        material = scene.m3_volume_noise_materials[materialIndex]
        col = layout.column(align=True)
        col.prop(material, "volumeDensity", text="Volume Density")
        col.prop(material, "nearPlane", text="Near Plane")
        col.prop(material, "falloff", text="Falloff")
        col.prop(material, "alphaTreshhold", text="Alpha Treshhold")
        col = layout.column_flow(columns=2)
        col.prop(material, "scrollRate", text="Scroll Rate")
        col.prop(material, "translation", text="Translation")
        col.prop(material, "scale", text="Scale")
        col.prop(material, "rotation", text="Rotation")


def displayMaterialPropertiesFlags(scene: bt.Scene, layout: bt.UILayout, materialReference):
    materialType = materialReference.materialType
    materialIndex = materialReference.materialIndex

    if materialType == shared.standardMaterialTypeIndex:
        material = scene.m3_standard_materials[materialIndex]
        col = layout.column_flow(columns=2)
        col.prop(material, "useVertexColor", text="Use Vertex Color")
        col.prop(material, "useVertexAlpha", text="Use Vertex Alpha")
        col.prop(material, "unknownFlag0x200", text="unknownFlag0x200")
        col.prop(material, "unfogged", text="Unfogged")
        col.prop(material, "twoSided", text="Two Sided")
        col.prop(material, "unshaded", text="Unshaded")
        col.prop(material, "noShadowsCast", text="No Shadows Cast")
        col.prop(material, "noHitTest", text="No Hit Test")
        col.prop(material, "noShadowsReceived", text="No Shadows Received")
        col.prop(material, "depthPrepass", text="Depth Prepass")
        col.prop(material, "useTerrainHDR", text="Use Terrain HDR")
        col.prop(material, "unknown0x400")
        col.prop(material, "simulateRoughness")
        col.prop(material, "perPixelForwardLighting", text="Soft Blending")
        col.prop(material, "depthFog")
        col.prop(material, "transparentShadows")
        col.prop(material, "decalLighting")
        col.prop(material, "transparencyDepthEffects")
        col.prop(material, "transparencyLocalLights")
        col.prop(material, "disableSoft", text="Disable Soft")
        col.prop(material, "darkNormalMapping", text="Dark Normal Mapping")
        col.prop(material, "hairLayerSorting")
        col.prop(material, "backgroundObject", text="Background Object")
        col.prop(material, "unknown0x8000000")
        col.prop(material, "excludeFromHighlighting", text="No Highlighting")
        col.prop(material, "clampOutput", text="Clamp Output")
        col.prop(material, "geometryVisible", text="Geometry Visible")
        col.prop(material, "acceptSplats", text="Accept Splats")
        sub = col.split()
        sub.active = material.acceptSplats
        sub.prop(material, "acceptSplatsOnly", text="Accept Splats Only")

        layout.label(text="Required On Low End:")
        col = layout.column_flow(columns=4)
        col.prop(material, "decalRequiredOnLowEnd", text="Decal")
        col.prop(material, "emissiveRequiredOnLowEnd", text="Emissive")
        col.prop(material, "specularRequiredOnLowEnd", text="Specular")
        col.prop(material, "zpFillRequiredOnLowEnd", text="ZP Fill")
    elif materialType == shared.volumeNoiseMaterialTypeIndex:
        material = scene.m3_volume_noise_materials[materialIndex]
        layout.prop(material, "drawAfterTransparency", text="Draw after transparency")


class MaterialPropertiesPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_material_properties"
    bl_label = "Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_material_references"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        ii = scene.m3_material_reference_index
        if ii < 0:
            return scene and False
        mat = scene.m3_material_references[ii]
        return scene and (mat.materialType != shared.stbMaterialTypeIndex and
                          mat.materialType != shared.lensFlareMaterialTypeIndex and
                          mat.materialType != shared.creepMaterialTypeIndex and
                          mat.materialType != shared.terrainMaterialTypeIndex)

    def draw(self, context):
        scene = context.scene
        materialReference = scene.m3_material_references[scene.m3_material_reference_index]

        layout = self.layout
        displayMaterialPropertiesUI(scene, layout, materialReference)


class ObjectMaterialPropertiesPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_object_material_properties"
    bl_label = "Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_material_selection"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        ob = context.object
        mat = scene.m3_material_references.get(ob.data.m3_material_name)
        return ob and mat is not None and (mat.materialType != shared.stbMaterialTypeIndex and
                                           mat.materialType != shared.lensFlareMaterialTypeIndex and
                                           mat.materialType != shared.creepMaterialTypeIndex and
                                           mat.materialType != shared.terrainMaterialTypeIndex)

    def draw(self, context):
        scene = context.scene

        layout = self.layout
        displayMaterialPropertiesUI(scene, layout, context.scene.m3_material_references.get(context.object.data.m3_material_name))


class MaterialPropertiesFlagsPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_material_properties_flags"
    bl_label = "Flags"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_material_properties"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return scene and (scene.m3_material_references[scene.m3_material_reference_index].materialType == shared.standardMaterialTypeIndex or
                          scene.m3_material_references[scene.m3_material_reference_index].materialType == shared.volumeNoiseMaterialTypeIndex)

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        materialIndex = scene.m3_material_reference_index
        if materialIndex >= 0 and materialIndex < len(scene.m3_material_references):
            materialReference = scene.m3_material_references[materialIndex]
            displayMaterialPropertiesFlags(scene, layout, materialReference)


class ObjectMaterialPropertiesFlagsPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_object_material_properties_flags"
    bl_label = "Flags"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_object_material_properties"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        ob = context.object
        return ob and (scene.m3_material_references.get(ob.data.m3_material_name).materialType == shared.standardMaterialTypeIndex or
                       scene.m3_material_references.get(ob.data.m3_material_name).materialType == shared.volumeNoiseMaterialTypeIndex)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mesh = context.object.data

        materialName = mesh.m3_material_name
        materialReference = scene.m3_material_references.get(materialName)
        if materialReference is not None:
            displayMaterialPropertiesFlags(scene, layout, materialReference)


def displayMaterialLayersUI(scene, layout, materialReference):
    materialType = materialReference.materialType
    materialIndex = materialReference.materialIndex
    row = layout.row()
    col = row.column()
    material = cm.getMaterial(scene, materialType, materialIndex)
    if material is not None:
        col.template_list("UI_UL_list", "m3_material_layers", material, "layers", scene, "m3_material_layer_index", rows=2)
        layerIndex = scene.m3_material_layer_index
        if layerIndex >= 0 and layerIndex < len(material.layers):
            layer = material.layers[layerIndex]
            layout.prop(layer, "colorEnabled", text="Texture Map Type")
            layout.prop(layer, "unknownbd3f7b5d", text="Unknown (id: bd3f7b5d)")


class MaterialLayersPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_material_layers"
    bl_label = "Layers"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_material_references"

    @classmethod
    def poll(cls, context):
        ii = context.scene.m3_material_reference_index
        if ii < 0:
            return context.scene and False
        mat = context.scene.m3_material_references[ii]
        return context.scene and mat.materialType != shared.compositeMaterialTypeIndex

    def draw(self, context):
        scene = context.scene
        materialReference = scene.m3_material_references[scene.m3_material_reference_index]

        layout = self.layout
        displayMaterialLayersUI(scene, layout, materialReference)


class ObjectMaterialLayersPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_object_material_layers"
    bl_label = "Layers"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_material_selection"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        ob = context.object
        matRef = scene.m3_material_references.get(ob.data.m3_material_name)
        return context.object and matRef is not None and matRef.materialType != shared.compositeMaterialTypeIndex

    def draw(self, context):
        scene = context.scene

        layout = self.layout
        displayMaterialLayersUI(scene, layout, scene.m3_material_references.get(context.object.data.m3_material_name))


def displayMaterialLayersColor(scene, layout, materialReference):
    materialType = materialReference.materialType
    materialIndex = materialReference.materialIndex
    material = cm.getMaterial(scene, materialType, materialIndex)

    layerIndex = scene.m3_material_layer_index
    if layerIndex >= 0 and layerIndex < len(material.layers):
        layer = material.layers[layerIndex]
        if layer.colorEnabled == "0":
            layout.prop(layer, "imagePath", text="Image Path")
            layout.prop(layer, "colorChannelSetting", text="Color Channels")
            row = layout.row()
            row.prop(layer, "invertColor", text="Invert Color")
            row.prop(layer, "clampColor", text="Clamp Color")
            row = layout.row()
            col = row.column(align=True)
            col.label(text="Brightness:")
            col.prop(layer, "brightness", text="")
            col.prop(layer, "brightMult", text="Multiplier")
            col.prop(layer, "midtoneOffset", text="Midtone Offset")
        else:
            layout.prop(layer, "color", text="Color")


class MaterialLayersColorPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_material_layers_color"
    bl_label = "Color"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_material_layers"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        materialIndex = scene.m3_material_reference_index
        if not(materialIndex >= 0 and materialIndex < len(scene.m3_material_references)):
            layout.label(text="No material has been selected")
            return
        materialReference = scene.m3_material_references[materialIndex]
        displayMaterialLayersColor(scene, layout, materialReference)


class ObjectMaterialLayersColorPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_object_material_layers_color"
    bl_label = "Color"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_object_material_layers"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        materialIndex = scene.m3_material_reference_index
        materialReference = scene.m3_material_references[materialIndex]
        materialType = materialReference.materialType
        material = cm.getMaterial(scene, materialType, materialIndex)

        if materialIndex >= 0 and materialIndex < len(scene.m3_material_references):
            layerIndex = scene.m3_material_layer_index
            if layerIndex >= 0 and layerIndex < len(material.layers):
                displayMaterialLayersColor(scene, layout, materialReference)


def displayMaterialLayersUv(scene, layout, materialReference):
    materialType = materialReference.materialType
    materialIndex = materialReference.materialIndex
    material = cm.getMaterial(scene, materialType, materialIndex)

    layerIndex = scene.m3_material_layer_index
    if layerIndex >= 0 and layerIndex < len(material.layers):
        layer = material.layers[layerIndex]
        layout.prop(layer, "uvSource", text="UV Source")
        isTriPlanarUVSource = layer.uvSource in ["16", "17", "18"]
        if isTriPlanarUVSource:
            row = layout.row()
            col = row.column(align=True)
            col.label(text="Tri Planar Offset:")
            col.prop(layer, "triPlanarOffset", index=0, text="X")
            col.prop(layer, "triPlanarOffset", index=1, text="Y")
            col.prop(layer, "triPlanarOffset", index=2, text="Z")
            col = row.column(align=True)
            col.label(text="Tri Planar Scale:")
            col.prop(layer, "triPlanarScale", index=0, text="X")
            col.prop(layer, "triPlanarScale", index=1, text="Y")
            col.prop(layer, "triPlanarScale", index=2, text="Z")
        else:
            row = layout.row()
            col = row.column(align=True)
            col.label(text="UV Offset:")
            col.prop(layer, "uvOffset", text="X", index=0)
            col.prop(layer, "uvOffset", text="Y", index=1)
            col.prop(layer, "textureWrapX", text="Tex. Wrap X")
            col = row.column(align=True)
            col.label(text="UV Tiling:")
            col.prop(layer, "uvTiling", text="X", index=0)
            col.prop(layer, "uvTiling", text="Y", index=1)
            col.prop(layer, "textureWrapY", text="Tex. Wrap Y")
            col = row.column(align=True)
            col.label(text="UV Angle:")
            col.prop(layer, "uvAngle", text="X", index=0)
            col.prop(layer, "uvAngle", text="Y", index=1)
            col.prop(layer, "uvAngle", text="Z", index=2)
        col = layout.column(align=True)
        col.label(text="Flipbook:")
        col.prop(layer, "flipBookRows", text="Rows")
        col.prop(layer, "flipBookColumns", text="Columns")
        col.prop(layer, "flipBookFrame", text="Frame")


class MaterialLayersUvPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_material_layers_uv"
    bl_label = "UV"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_material_layers"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        matRef = scene.m3_material_references[scene.m3_material_reference_index]
        mat = cm.getMaterial(scene, matRef.materialType, matRef.materialIndex)
        return mat.layers[scene.m3_material_layer_index].colorEnabled == "0"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        materialIndex = scene.m3_material_reference_index
        materialReference = scene.m3_material_references[materialIndex]
        displayMaterialLayersUv(scene, layout, materialReference)


class ObjectMaterialLayersUvPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_object_material_layers_uv"
    bl_label = "UV"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_object_material_layers"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        ob = context.object
        matRef = scene.m3_material_references.get(ob.data.m3_material_name)
        mat = cm.getMaterial(scene, matRef.materialType, matRef.materialIndex)
        return context.object and mat.layers[scene.m3_material_layer_index].colorEnabled == "0"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        meshObject = context.object
        mesh = meshObject.data
        materialName = mesh.m3_material_name
        materialRefName = scene.m3_material_references.get(materialName)

        if materialRefName is None:
            layout.label(text="No properties to display")
            return

        materialIndex = scene.m3_material_reference_index
        materialReference = scene.m3_material_references[materialIndex]
        materialType = materialReference.materialType
        material = cm.getMaterial(scene, materialType, materialIndex)

        if materialIndex >= 0 and materialIndex < len(scene.m3_material_references):
            materialReference = scene.m3_material_references[materialIndex]

            layerIndex = scene.m3_material_layer_index
            if layerIndex >= 0 and layerIndex < len(material.layers):
                displayMaterialLayersUv(scene, layout, materialReference)


def displayMaterialLayersFresnel(scene, layout, materialReference):
    materialType = materialReference.materialType
    materialIndex = materialReference.materialIndex
    material = cm.getMaterial(scene, materialType, materialIndex)

    layerIndex = scene.m3_material_layer_index
    if layerIndex >= 0 and layerIndex < len(material.layers):
        layer = material.layers[layerIndex]
        col = layout.column(align=True)
        col.prop(layer, "fresnelType", text="Fresnel")
        box = col.box()
        box.active = (layer.fresnelType != "0")
        brow = box.row()
        bcol = brow.column(align=True)
        bcol.label(text="Power:")
        bcol.prop(layer, "fresnelExponent", text="Exponent")
        bcol.prop(layer, "fresnelMin", text="Min")
        bcol.prop(layer, "fresnelMax", text="Max")
        bcol = brow.column(align=True)
        bcol.label(text="Mask:")
        bcol.prop(layer, "fresnelMaskX", text="X", slider=True)
        bcol.prop(layer, "fresnelMaskY", text="Y", slider=True)
        bcol.prop(layer, "fresnelMaskZ", text="Z", slider=True)
        bcol = brow.column(align=True)
        bcol.label(text="Rotation:")
        bcol.prop(layer, "fresnelRotationYaw", text="Yaw")
        bcol.prop(layer, "fresnelRotationPitch", text="Pitch")
        brow = box.row()
        brow.prop(layer, "fresnelLocalTransform", text="Local Transform")
        brow.prop(layer, "fresnelDoNotMirror", text="Do Not Mirror")


class MaterialLayersFresnelPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_material_layers_fresnel"
    bl_label = "Fresnel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_material_layers"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_material_reference_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        materialIndex = scene.m3_material_reference_index
        materialReference = scene.m3_material_references[materialIndex]
        displayMaterialLayersFresnel(scene, layout, materialReference)


class ObjectMaterialLayersFresnelPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_object_material_layers_fresnel"
    bl_label = "Fresnel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_object_material_layers"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        meshObject = context.object
        mesh = meshObject.data
        materialName = mesh.m3_material_name
        materialRefName = scene.m3_material_references.get(materialName)

        if materialRefName is None:
            layout.label(text="No properties to display")
            return

        materialIndex = scene.m3_material_reference_index
        if materialIndex >= 0 and materialIndex < len(scene.m3_material_references):
            materialReference = scene.m3_material_references[materialIndex]
            displayMaterialLayersFresnel(scene, layout, materialReference)


def displayMaterialLayersRTT(scene, layout, materialReference):
    materialType = materialReference.materialType
    materialIndex = materialReference.materialIndex
    material = cm.getMaterial(scene, materialType, materialIndex)

    layerIndex = scene.m3_material_layer_index
    if layerIndex >= 0 and layerIndex < len(material.layers):
        layer = material.layers[layerIndex]
        col = layout.column(align=True)
        col.active = shared.isVideoFilePath(layer.imagePath)
        col.prop(layer, "rttChannel", text="RTT Channel")
        box = col.box()
        box.active = layer.rttChannel != "-1"
        brow = box.row()
        bcol = brow.column(align=True)
        bcol.prop(layer, "videoFrameRate", text="Frame Rate")
        bcol.prop(layer, "videoStartFrame", text="Start Frame")
        bcol.prop(layer, "videoEndFrame", text="End Frame")
        bcol = brow.column(align=True)
        bcol.prop(layer, "videoMode", text="Mode")
        sub = bcol.column_flow(columns=2)
        sub.prop(layer, "videoSyncTiming", text="Sync Timing")
        sub.prop(layer, "videoPlay", text="Play")
        sub.prop(layer, "videoRestart", text="Restart")


class MaterialLayersRTTPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_material_layers_rtt"
    bl_label = "RTT"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_material_layers"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        matRef = scene.m3_material_references[scene.m3_material_reference_index]
        mat = cm.getMaterial(scene, matRef.materialType, matRef.materialIndex)
        return mat.layers[scene.m3_material_layer_index].colorEnabled == "0"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        materialIndex = scene.m3_material_reference_index
        if not(materialIndex >= 0 and materialIndex < len(scene.m3_material_references)):
            layout.label(text="No material has been selected")
            return
        materialReference = scene.m3_material_references[materialIndex]
        displayMaterialLayersRTT(scene, layout, materialReference)


class ObjectMaterialLayersRTTPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_object_material_layers_rtt"
    bl_label = "RTT"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_object_material_layers"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        ob = context.object
        matRef = scene.m3_material_references.get(ob.data.m3_material_name)
        mat = cm.getMaterial(scene, matRef.materialType, matRef.materialIndex)
        return context.object and mat.layers[scene.m3_material_layer_index].colorEnabled == "0"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        meshObject = context.object
        mesh = meshObject.data
        materialName = mesh.m3_material_name
        materialRefName = scene.m3_material_references.get(materialName)

        if materialRefName is None:
            layout.label(text="No properties to display")
            return

        materialIndex = scene.m3_material_reference_index
        if materialIndex >= 0 and materialIndex < len(scene.m3_material_references):
            materialReference = scene.m3_material_references[materialIndex]
            displayMaterialLayersRTT(scene, layout, materialReference)


class CameraPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_cameras"
    bl_label = "M3 Cameras"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        rows = 2
        if len(scene.m3_cameras) == 1:
            rows = 3
        if len(scene.m3_cameras) > 1:
            rows = 5

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_cameras", scene, "m3_cameras", scene, "m3_camera_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.cameras_add", icon="ADD", text="")
        col.operator("m3.cameras_remove", icon="REMOVE", text="")

        if len(scene.m3_cameras) > 0:
            col.separator()
            col.menu("OBJECT_MT_M3_cameras", icon="DOWNARROW_HLT", text="")

        if len(scene.m3_cameras) > 1:
            col.separator()
            col.operator("m3.cameras_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.cameras_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_camera_index
        if currentIndex >= 0:
            camera = scene.m3_cameras[currentIndex]
            col = layout.column(align=True)
            col.prop(camera, "name", text="Name")
            col.prop(camera, "fieldOfView", text="Field Of View")
            col.prop(camera, "farClip", text="Far Clip")
            col.prop(camera, "nearClip", text="Near Clip")
            col.prop(camera, "clip2", text="Clip 2")
            col.prop(camera, "focalDepth", text="Focal Depth")
            col.prop(camera, "falloffStart", text="Falloff Start")
            col.prop(camera, "falloffEnd", text="Falloff End")
            col.prop(camera, "depthOfField", text="Depth Of Field")


class ParticleSystemsPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_particles"
    bl_label = "M3 Particle Systems"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        particleSystems = len(scene.m3_particle_systems)

        rows = 2
        if particleSystems == 1:
            rows = 3
        if particleSystems > 1:
            rows = 5

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_particle_systems", scene, "m3_particle_systems", scene, "m3_particle_system_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.particle_systems_add", icon="ADD", text="")
        col.operator("m3.particle_systems_remove", icon="REMOVE", text="")

        if particleSystems > 0:
            col.separator()
            col.menu("OBJECT_MT_M3_particle_systems", icon="DOWNARROW_HLT", text="")

        if particleSystems > 1:
            col.separator()
            col.operator("m3.particle_systems_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.particle_systems_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_particle_system_index
        if currentIndex >= 0:
            particle_system = scene.m3_particle_systems[currentIndex]
            layout.prop(particle_system, "name", text="Name")
            row = layout.row(align=True)
            row.prop(particle_system, "emissionRate", text="Particles Rate")
            row.prop(particle_system, "partEmit", text="Particles Create")


class ParticleSystemCopiesPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_particle_copies"
    bl_label = "Copies"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_particles"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_particle_system_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        particleSystemIndex = scene.m3_particle_system_index
        particle_system = scene.m3_particle_systems[particleSystemIndex]
        copyIndex = particle_system.copyIndex
        copies = len(particle_system.copies)

        rows = 2
        if copies > 1:
            rows = 4

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_particle_system_copies", particle_system, "copies", particle_system, "copyIndex", rows=rows)

        col = row.column(align=True)
        col.operator("m3.particle_system_copies_add", icon="ADD", text="")
        col.operator("m3.particle_system_copies_remove", icon="REMOVE", text="")

        if copies > 1:
            col.separator()
            col.operator("m3.particle_system_copies_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.particle_system_copies_move", icon="TRIA_DOWN", text="").shift = 1

        if copyIndex >= 0:
            copy = particle_system.copies[copyIndex]
            layout.prop(copy, "name", text="Name")
            row = layout.row(align=True)
            row.prop(copy, "emissionRate", text="Particles Rate")
            row.prop(copy, "partEmit", text="Particles Create")


class ParticleSystemsPropPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_particles_prop"
    bl_label = "Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_content = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_particles"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_particle_system_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        particle_system = scene.m3_particle_systems[scene.m3_particle_system_index]
        layout.prop_search(particle_system, "materialName", scene, "m3_material_references", text="Material", icon="NONE")
        layout.prop(particle_system, "particleType", text="Particle Type")
        row = layout.row()
        col = row.column()
        sub = col.row(align=True)
        sub.label(text="LOD Reduce/Cut:")
        sub.prop(particle_system, "lodReduce", text="")
        sub.prop(particle_system, "lodCut", text="")
        sub = col.column(align=True)
        col.prop(particle_system, "maxParticles", text="Particle Maximum")
        sub = col.split(align=True)
        sub.active = particle_system.particleType in ["1", "6"]
        sub.prop(particle_system, "lengthWidthRatio", text="Length/Width Ratio")
        row = layout.row()
        col = row.column()
        subrow = col.row(align=True)
        subrow.label(text="Lifespan:")
        subrow.prop(particle_system, "randomizeWithLifespan2", text="Randomize")
        subrow = col.row(align=True)
        subrow.prop(particle_system, "lifespan1", text="")
        sub = subrow.split(align=True)
        sub.active = particle_system.randomizeWithLifespan2
        sub.prop(particle_system, "lifespan2", text="")
        col = row.column()
        subrow = col.row(align=True)
        subrow.label(text="Mass:")
        subrow.prop(particle_system, "randomizeWithMass2", text="Randomize")
        subrow = col.row(align=True)
        subrow.prop(particle_system, "mass", text="")
        sub = subrow.split(align=True)
        sub.active = particle_system.randomizeWithMass2
        sub.prop(particle_system, "mass2", text="")
        row = layout.row()
        col = row.column()
        col.prop_search(particle_system, "trailingParticlesName", scene, "m3_particle_systems", text="Trailing Particles", icon="NONE")
        sub = col.split(align=True)
        sub.active = particle_system.trailingParticlesName != ""
        sub.prop(particle_system, "trailingParticlesChance", text="Chance to trail")
        sub.prop(particle_system, "trailingParticlesRate", text="Tailing  Rate")
        # layout.prop(particle_system, "unknownFloat2c", text="Unknown f2c")
        # layout.prop(particle_system, "unknownFloat6", text="Unknown Float 6")
        # layout.prop(particle_system, "unknownFloat7", text="Unknown Float 7")


class ParticleSystemsAreaPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_particles_area"
    bl_label = "Area"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_content = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_particles"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_particle_system_index >= 0

    def draw(self, context):
        scene = context.scene
        particle_system = scene.m3_particle_systems[scene.m3_particle_system_index]
        layout = self.layout
        layout.prop(particle_system, "killSphere", text="System Limit Radius")
        row = layout.row()
        col = row.column(align=True)
        col.prop(particle_system, "emissionAreaType", text="Area")
        sub = col.split(align=True)
        sub.active = particle_system.emissionAreaType in emissionAreaTypesWithLength
        sub.prop(particle_system, "emissionAreaSize", index=0, text="Length")
        sub = col.split(align=True)
        sub.active = particle_system.emissionAreaType in emissionAreaTypesWithWidth
        sub.prop(particle_system, "emissionAreaSize", index=1, text="Width")
        sub = col.split(align=True)
        sub.active = particle_system.emissionAreaType in emissionAreaTypesWithHeight
        sub.prop(particle_system, "emissionAreaSize", index=2, text="Height")
        sub = col.split(align=True)
        sub.active = particle_system.emissionAreaType in emissionAreaTypesWithRadius
        sub.prop(particle_system, "emissionAreaRadius", text="Radius")
        col = row.column(align=True)
        col.prop(particle_system, "cutoutEmissionArea", text="Cutout:")
        sub = col.split(align=True)
        sub.active = particle_system.cutoutEmissionArea and particle_system.emissionAreaType in emissionAreaTypesWithLength
        sub.prop(particle_system, "emissionAreaCutoutSize", index=0, text="Length")
        sub = col.split(align=True)
        sub.active = particle_system.cutoutEmissionArea and particle_system.emissionAreaType in emissionAreaTypesWithWidth
        sub.prop(particle_system, "emissionAreaCutoutSize", index=1, text="Width")
        sub = col.split(align=True)
        sub.active = particle_system.cutoutEmissionArea and particle_system.emissionAreaType == shared.emissionAreaTypeCuboid
        # property has no effect on cylinder cutout
        sub.prop(particle_system, "emissionAreaCutoutSize", index=2, text="Height")
        sub = col.split(align=True)
        sub.active = particle_system.cutoutEmissionArea and particle_system.emissionAreaType in emissionAreaTypesWithRadius
        sub.prop(particle_system, "emissionAreaCutoutRadius", text="Radius")
        row = layout.row()
        row.active = particle_system.emissionAreaType == shared.emissionAreaTypeMesh
        # FIXME Add button to set mesh
        row.operator("m3.create_spawn_points_from_mesh", text="Spawn Points From Mesh")


class ParticleSystemsMovementPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_particles_movement"
    bl_label = "Movement"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_content = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_particles"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_particle_system_index >= 0

    def draw(self, context):
        scene = context.scene
        particle_system = context.scene.m3_particle_systems[scene.m3_particle_system_index]
        layout = self.layout
        layout.prop(particle_system, "emissionType", text="Emission Type")
        layout.label(text="Velocity:")
        row = layout.row()
        col = row.column(align=True)
        col.prop(particle_system, "randomizeWithEmissionSpeed2", text="Randomize")
        col.prop(particle_system, "emissionSpeed1", text="")
        sub = col.split(align=True)
        sub.active = particle_system.randomizeWithEmissionSpeed2
        sub.prop(particle_system, "emissionSpeed2", text="")
        col = row.column(align=True)
        col.label(text="Angle:")
        col.prop(particle_system, "emissionAngleX", text="X")
        col.prop(particle_system, "emissionAngleY", text="Y")
        col = row.column(align=True)
        col.label(text="Spread:")
        col.prop(particle_system, "emissionSpreadX", text="X")
        col.prop(particle_system, "emissionSpreadY", text="Y")
        row = layout.row()
        col = row.column(align=True)
        col.prop(particle_system, "bounce", text="Bounce")
        col.prop(particle_system, "friction", text="Friction")
        col.prop(particle_system, "drag", text="Drag")
        col.prop(particle_system, "zAcceleration", text="Z-Acceleration")
        col.prop(particle_system, "windMultiplier", text="Wind Multiplier")
        col = row.column(align=True)
        col.label(text="Noise:")
        col.prop(particle_system, "noiseAmplitude", text="Amplitude")
        col.prop(particle_system, "noiseFrequency", text="Frequency")
        col.prop(particle_system, "noiseCohesion", text="Cohesion")
        col.prop(particle_system, "noiseEdge", text="Edge")
        row = layout.row()
        col = row.column()
        col.label(text="Local Force Channels:")
        col.prop(particle_system, "localForceChannels", text="")
        col = row.column()
        col.label(text="World Force Channels:")
        col.prop(particle_system, "worldForceChannels", text="")


class ParticleSystemsColorPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_particles_color"
    bl_label = "Color"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_content = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_particles"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_particle_system_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        particle_system = scene.m3_particle_systems[scene.m3_particle_system_index]

        row = layout.row()
        col = row.column(align=True)
        col.label(text="Color:")
        col.label(text="Initial:")
        col.label(text="Middle:")
        col.label(text="Final:")
        col = row.column(align=True)
        col.label(text="")
        col.prop(particle_system, "initialColor1", text="")
        col.prop(particle_system, "middleColor1", text="")
        col.prop(particle_system, "finalColor1", text="")
        col = row.column(align=True)
        col.prop(particle_system, "randomizeWithColor2", text="Randomize")
        sub = col.column(align=True)
        sub.active = particle_system.randomizeWithColor2
        sub.prop(particle_system, "initialColor2", text="")
        sub.prop(particle_system, "middleColor2", text="")
        sub.prop(particle_system, "finalColor2", text="")
        layout.prop(particle_system, "colorSmoothingType", text="Smoothing Type")
        row = layout.row()
        col = row.column(align=True)
        col.prop(particle_system, "colorAnimationMiddle", text="Color Middle")
        col.prop(particle_system, "alphaAnimationMiddle", text="Alpha Middle")
        col = row.column(align=True)
        col.active = particle_system.colorSmoothingType in ["3", "4"]
        col.prop(particle_system, "colorHoldTime", text="Color Hold Time")
        col.prop(particle_system, "alphaHoldTime", text="Alpha Hold Time")


class ParticleSystemsSizePanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_particles_size"
    bl_label = "Scale"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_content = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_particles"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_particle_system_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        particle_system = scene.m3_particle_systems[scene.m3_particle_system_index]

        row = layout.row()
        col = row.column(align=True)
        col.label(text="Size (Particle):")
        col.prop(particle_system, "particleSizes1", index=0, text="Initial")
        col.prop(particle_system, "particleSizes1", index=1, text="Middle")
        col.prop(particle_system, "particleSizes1", index=2, text="Final")
        col = row.column(align=True)
        col.prop(particle_system, "randomizeWithParticleSizes2", text="Randomize With:")
        sub = col.column(align=True)
        sub.active = particle_system.randomizeWithParticleSizes2
        sub.prop(particle_system, "particleSizes2", index=0, text="Initial")
        sub.prop(particle_system, "particleSizes2", index=1, text="Middle")
        sub.prop(particle_system, "particleSizes2", index=2, text="Final")
        layout.prop(particle_system, "sizeSmoothingType", text="Smoothing Type")
        row = layout.row()
        row.prop(particle_system, "sizeAnimationMiddle", text="Size Middle")
        sub = row.split()
        sub.active = particle_system.sizeSmoothingType in ["3", "4"]
        sub.prop(particle_system, "sizeHoldTime", text="Size Hold Time")


class ParticleSystemsRotationPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_particles_rotation"
    bl_label = "Rotation"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_content = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_particles"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_particle_system_index >= 0

    def draw(self, context):

        layout = self.layout
        scene = context.scene
        particle_system = scene.m3_particle_systems[scene.m3_particle_system_index]

        row = layout.row()
        col = row.column(align=True)
        col.label(text="Rotation (Particle):")
        col.prop(particle_system, "rotationValues1", index=0, text="Initial")
        col.prop(particle_system, "rotationValues1", index=1, text="Middle")
        col.prop(particle_system, "rotationValues1", index=2, text="Final")
        col = row.column(align=True)
        col.prop(particle_system, "randomizeWithRotationValues2", text="Randomize With:")
        sub = col.column(align=True)
        sub.active = particle_system.randomizeWithRotationValues2
        sub.prop(particle_system, "rotationValues2", index=0, text="Initial")
        sub.prop(particle_system, "rotationValues2", index=1, text="Middle")
        sub.prop(particle_system, "rotationValues2", index=2, text="Final")
        layout.prop(particle_system, "rotationSmoothingType", text="Smoothing Type")
        row = layout.row()
        row.prop(particle_system, "rotationAnimationMiddle", text="Rotation Middle")
        sub = row.split()
        sub.active = particle_system.rotationSmoothingType in ["3", "4"]
        sub.prop(particle_system, "rotationHoldTime", text="Rotation Hold Time")


class ParticleSystemsImageAnimPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_particles_imageanim"
    bl_label = "Image Animation"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_content = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_particles"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_particle_system_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        row = layout.row()
        particle_system = scene.m3_particle_systems[scene.m3_particle_system_index]
        split = layout.split()
        row = split.row()
        sub = row.column(align=True)
        sub.label(text="Column:")
        sub.prop(particle_system, "numberOfColumns", text="Count")
        sub.prop(particle_system, "columnWidth", text="Width")
        row = split.row()
        sub = row.column(align=True)
        sub.label(text="Row:")
        sub.prop(particle_system, "numberOfRows", text="Count")
        sub.prop(particle_system, "rowHeight", text="Height")
        split = layout.split()
        row = split.row()
        sub = row.column(align=True)
        sub.label(text="Phase 1 Image Index:")
        sub.prop(particle_system, "phase1StartImageIndex", text="Inital")
        sub.prop(particle_system, "phase1EndImageIndex", text="Final")
        row = split.row()
        sub = row.column(align=True)
        sub.label(text="Phase 2 Image Index:")
        sub.prop(particle_system, "phase2StartImageIndex", text="Inital")
        sub.prop(particle_system, "phase2EndImageIndex", text="Final")
        layout.prop(particle_system, "relativePhase1Length", text="Relative Phase 1 Length")


class ParticleSystemsFlagsPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_particles_flags"
    bl_label = "Flags"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_content = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_particles"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_particle_system_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        particle_system = scene.m3_particle_systems[scene.m3_particle_system_index]
        col = layout.column_flow(columns=2)
        col.prop(particle_system, "trailingEnabled", text="Trailing")
        col.prop(particle_system, "sort", text="Sort")
        col.prop(particle_system, "collideTerrain", text="Collide Terrain")
        col.prop(particle_system, "collideObjects", text="Collide Objects")
        col.prop(particle_system, "spawnOnBounce", text="Spawn On Bounce")
        col.prop(particle_system, "inheritEmissionParams", text="Inherit Emission Params")
        col.prop(particle_system, "inheritParentVel", text="Inherit Parent Vel")
        col.prop(particle_system, "sortByZHeight", text="Sort By Z Height")
        col.prop(particle_system, "reverseIteration", text="Reverse Iteration")
        col.prop(particle_system, "litParts", text="Lit Parts")
        col.prop(particle_system, "randFlipBookStart", text="Rand Flip Book Start")
        col.prop(particle_system, "multiplyByGravity", text="Multiply By Gravity")
        col.prop(particle_system, "clampTailParts", text="Clamp Tail Parts")
        col.prop(particle_system, "spawnTrailingParts", text="Spawn Trailing Parts")
        col.prop(particle_system, "fixLengthTailParts", text="Fix Length Tail Parts")
        col.prop(particle_system, "useVertexAlpha", text="Use Vertex Alpha")
        col.prop(particle_system, "modelParts", text="Model Parts")
        col.prop(particle_system, "swapYZonModelParts", text="Swap Y Z On Model Parts")
        col.prop(particle_system, "scaleTimeByParent", text="Scale Time By Parent")
        col.prop(particle_system, "useLocalTime", text="Use Local Time")
        col.prop(particle_system, "simulateOnInit", text="Simulate On Init")
        col.prop(particle_system, "copy", text="Copy")


class RibbonsPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_ribbons"
    bl_label = "M3 Ribbons"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        rows = 2
        if len(scene.m3_ribbons) == 1:
            rows = 3
        if len(scene.m3_ribbons) > 1:
            rows = 5

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_ribbons", scene, "m3_ribbons", scene, "m3_ribbon_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.ribbons_add", icon="ADD", text="")
        col.operator("m3.ribbons_remove", icon="REMOVE", text="")

        if len(scene.m3_ribbons) > 0:
            col.separator()
            col.menu("OBJECT_MT_M3_ribbons", icon="DOWNARROW_HLT", text="")

        if len(scene.m3_ribbons) > 1:
            col.separator()
            col.operator("m3.ribbons_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.ribbons_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_ribbon_index
        if currentIndex >= 0:
            ribbon = scene.m3_ribbons[currentIndex]
            layout.separator()
            layout.prop(ribbon, "name", text="Name")


class RibbonPropertiesPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_ribbon_prop"
    bl_label = "Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_ribbons"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_ribbon_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        ribbonIndex = scene.m3_ribbon_index
        if ribbonIndex < 0 or ribbonIndex >= len(scene.m3_ribbons):
            return
        ribbon = scene.m3_ribbons[ribbonIndex]
        layout.prop_search(ribbon, "materialName", scene, "m3_material_references", text="Material", icon="NONE")
        row = layout.row()
        row.prop(ribbon, "ribbonType", text="Type")
        col = row.column()
        col.active = len(ribbon.endPoints) == 0
        col.prop(ribbon, "active", text="Active")
        sub = layout.column()
        sub.active = ribbon.ribbonType == "3"
        sub.prop(ribbon, "starRatio", text="Star Ratio")
        row = layout.row()
        row.label(text="LOD Reduce/Cut:")
        row.prop(ribbon, "lodReduce", text="")
        row.prop(ribbon, "lodCut", text="")
        col = layout.column(align=True)
        col.active = len(ribbon.endPoints) == 0
        col.prop(ribbon, "cullType", text="Lifespan Type")
        sub = col.column(align=True)
        sub.active = ribbon.cullType == "0"
        sub.prop(ribbon, "lifespan", text="Lifespan")
        sub = col.column(align=True)
        sub.prop(ribbon, "length")
        col = layout.column(align=True)
        col.prop(ribbon, "ribbonDivisions", text="Divisions")
        col.prop(ribbon, "ribbonSides", text="Sides")
        col = layout.column(align=True)
        col.active = len(ribbon.endPoints) == 0
        col.prop(ribbon, "drag", text="Drag")
        col.prop(ribbon, "friction", text="Friction")
        col.prop(ribbon, "bounce", text="Bounce")
        col.prop(ribbon, "mass", text="Mass")
        col.prop(ribbon, "gravity", text="Gravity")
        row = layout.row()
        col = row.column(align=True)
        col.active = len(ribbon.endPoints) == 0
        col.prop(ribbon, "yaw", text="Yaw")
        col.prop(ribbon, "yawVariationType", text="Variation")
        sub = col.column(align=True)
        sub.active = ribbon.yawVariationType != "0"
        sub.prop(ribbon, "yawVariationAmplitude", text="Amplitude")
        sub.prop(ribbon, "yawVariationFrequency", text="Frequency")
        col = row.column(align=True)
        col.active = len(ribbon.endPoints) == 0
        col.prop(ribbon, "pitch", text="Pitch")
        col.prop(ribbon, "pitchVariationType", text="Variation")
        sub = col.column(align=True)
        sub.active = ribbon.pitchVariationType != "0"
        sub.prop(ribbon, "pitchVariationAmplitude", text="Amplitude")
        sub.prop(ribbon, "pitchVariationFrequency", text="Frequency")
        col = layout.column(align=True)
        col.active = len(ribbon.endPoints) == 0
        col.label(text="Rotation:")
        col.prop(ribbon, "rotation", index=0, text="Start")
        col.prop(ribbon, "rotation", index=1, text="Middle")
        col.prop(ribbon, "rotation", index=2, text="End")
        col = layout.column(align=True)
        col.active = len(ribbon.endPoints) == 0
        col.prop(ribbon, "rotationMiddleTime", text="Rotation Middle Time")
        col.prop(ribbon, "rotationMiddleHoldTime")
        col = layout.column(align=True)
        col.label(text="Noise:")
        col.prop(ribbon, "surfaceNoiseAmplitude", text="Amplitude")
        col.prop(ribbon, "surfaceNoiseNumberOfWaves", text="Waves")
        col.prop(ribbon, "surfaceNoiseFrequency", text="Frequency")
        col.prop(ribbon, "surfaceNoiseScale", text="Scale")
        col = layout.column(align=True)
        col.prop(ribbon, "parentVelocity")
        col.prop(ribbon, "overlayPhase")


class RibbonColorPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_ribbon_color"
    bl_label = "Color"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_ribbons"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_ribbon_index >= 0 and context.scene.m3_ribbon_index < len(context.scene.m3_ribbons)

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        ribbon = scene.m3_ribbons[scene.m3_ribbon_index]
        col = layout.column_flow(align=True, columns=2)
        col.label(text="Base:")
        col.label(text="Center:")
        col.label(text="Tip:")
        col.prop(ribbon, "baseColoring", text="")
        col.prop(ribbon, "centerColoring", text="")
        col.prop(ribbon, "tipColoring", text="")
        col = layout.column(align=True)
        col.prop(ribbon, "colorSmoothing", text="Color Smoothing")
        col.prop(ribbon, "colorMiddleTime", text="Color Middle Time")
        col.prop(ribbon, "colorMiddleHoldTime", text="Color Middle Hold Time")
        col.prop(ribbon, "alphaMiddleTime", text="Alpha Animation Middle")
        col.prop(ribbon, "alphaMiddleHoldTime")
        col = layout.column(align=True)
        col.prop(ribbon, "alphaVariationType", text="Alpha Variation")
        sub = col.column(align=True)
        sub.active = ribbon.alphaVariationType != "0"
        sub.prop(ribbon, "alphaVariationAmplitude", text="Amplitude")
        sub.prop(ribbon, "alphaVariationFrequency", text="Frequency")


class RibbonScalePanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_ribbon_scale"
    bl_label = "Scale"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_ribbons"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_ribbon_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        ribbonIndex = scene.m3_ribbon_index
        if ribbonIndex < 0 or ribbonIndex >= len(scene.m3_ribbons):
            return
        ribbon = scene.m3_ribbons[ribbonIndex]
        row = layout.row()
        col = row.column(align=True)
        col.active = len(ribbon.endPoints) == 0
        col.label(text="Speed:")
        col.prop(ribbon, "speed")
        col.prop(ribbon, "speedVariationType", text="Variation")
        sub = col.column(align=True)
        sub.active = ribbon.speedVariationType != "0"
        sub.prop(ribbon, "speedVariationAmplitude", text="Amplitude")
        sub.prop(ribbon, "speedVariationFrequency", text="Frequency")
        col = row.column(align=True)
        col.label(text="Size:")
        col.prop(ribbon, "size", index=0, text="Start")
        col.prop(ribbon, "size", index=1, text="Middle")
        col.prop(ribbon, "size", index=2, text="End")
        col.prop(ribbon, "sizeVariationType", text="Variation")
        sub = col.column(align=True)
        sub.active = ribbon.sizeVariationType != "0"
        sub.prop(ribbon, "sizeVariationAmplitude", text="Amplitude")
        sub.prop(ribbon, "sizeVariationFrequency", text="Frequency")
        col = layout.column(align=True)
        col.prop(ribbon, "sizeSmoothing", text="Size Smoothing")
        col.prop(ribbon, "sizeMiddleTime", text="Size Middle Time")
        col.prop(ribbon, "sizeMiddleHoldTime", text="Size Middle Hold Time")


class RibbonFlagsPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_ribbon_flags"
    bl_label = "Flags"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_ribbons"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_ribbon_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ribbon = scene.m3_ribbons[scene.m3_ribbon_index]
        col = layout.column()
        col.active = len(ribbon.endPoints) == 0
        col.label(text="Local Force Channels:")
        col.prop(ribbon, "localForceChannels", text="")
        col = layout.column()
        col.active = len(ribbon.endPoints) == 0
        col.label(text="World Force Channels:")
        col.prop(ribbon, "worldForceChannels", text="")
        col = layout.column_flow(columns=2)
        col.prop(ribbon, "collideWithTerrain", text="Collide With Terrain")
        col.prop(ribbon, "collideWithObjects", text="Collide With Objects")
        col.prop(ribbon, "edgeFalloff", text="Edge Falloff")
        col.prop(ribbon, "inheritParentVelocity", text="Inherit Parent Velocity")
        col.prop(ribbon, "smoothSize", text="Smooth Size")
        col.prop(ribbon, "bezierSmoothSize", text="Bezier Smooth Size")
        col.prop(ribbon, "useVertexAlpha", text="Use Vertex Alpha")
        col.prop(ribbon, "scaleTimeByParent", text="Scale Time By Parent")
        col.prop(ribbon, "forceCPUSimulation", text="Force Legacy")
        col.prop(ribbon, "useLocaleTime", text="Use Locale Time")
        col.prop(ribbon, "simulateOnInitialization", text="Simulate On Initialization")
        col.prop(ribbon, "useLengthAndTime", text="Use Length And Time")
        col.prop(ribbon, "accurateGPUTangents", text="Accurate GPU tangents")
        col.prop(ribbon, "worldSpace", text="World Space")


class RibbonEndPointsPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_ribbon_end_points"
    bl_label = "Splines"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_ribbons"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_ribbon_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        ribbon = scene.m3_ribbons[scene.m3_ribbon_index]

        rows = 2
        if len(ribbon.endPoints) > 1:
            rows = 4

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_ribbon_end_points", ribbon, "endPoints", ribbon, "endPointIndex", rows=rows)

        col = row.column(align=True)
        col.operator("m3.ribbon_end_points_add", icon="ADD", text="")
        col.operator("m3.ribbon_end_points_remove", icon="REMOVE", text="")

        if len(ribbon.endPoints) > 1:
            col.separator()
            col.operator("m3.ribbon_end_points_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.ribbon_end_points_move", icon="TRIA_DOWN", text="").shift = 1

        endPointIndex = ribbon.endPointIndex
        if ribbon.endPointIndex >= 0:
            endPoint = ribbon.endPoints[endPointIndex]
            layout.prop(endPoint, "name", text="Bone Name")
            col = layout.column(align=True)
            col.prop(endPoint, "tangent1", text="Tangent 1")
            col.prop(endPoint, "tangent2", text="Tangent 2")
            col.prop(endPoint, "tangent3", text="Tangent 3")
            layout.separator()
            col = layout.column(align=True)
            col.prop(endPoint, "yaw", text="Yaw")
            col.prop(endPoint, "yawVariationType", text="Variation Type")
            sub = col.column(align=True)
            sub.active = endPoint.yawVariationType != "0"
            sub.prop(endPoint, "yawVariationAmplitude", text="Amplitude")
            sub.prop(endPoint, "yawVariationFrequency", text="Frequency")
            layout.separator()
            col = layout.column(align=True)
            col.prop(endPoint, "pitch", text="Pitch")
            col.prop(endPoint, "pitchVariationType", text="Variation Type")
            sub = col.column(align=True)
            sub.active = endPoint.pitchVariationType != "0"
            sub.prop(endPoint, "pitchVariationAmplitude", text="Amplitude")
            sub.prop(endPoint, "pitchVariationFrequency", text="Frequency")
            layout.separator()
            col = layout.column(align=True)
            col.prop(endPoint, "length", text="Length")
            col.prop(endPoint, "speedVariationType", text="Variation Type")
            sub = col.column(align=True)
            sub.active = endPoint.speedVariationType != "0"
            sub.prop(endPoint, "speedVariationAmplitude", text="Amplitude")
            sub.prop(endPoint, "speedVariationFrequency", text="Frequency")


class ForcePanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_forces"
    bl_label = "M3 Forces"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        rows = 2
        if len(scene.m3_forces) == 1:
            rows = 3
        if len(scene.m3_forces) > 1:
            rows = 5

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_forces", scene, "m3_forces", scene, "m3_force_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.forces_add", icon="ADD", text="")
        col.operator("m3.forces_remove", icon="REMOVE", text="")

        if len(scene.m3_forces) > 0:
            col.separator()
            col.menu("OBJECT_MT_M3_forces", icon="DOWNARROW_HLT", text="")

        if len(scene.m3_forces) > 1:
            col.separator()
            col.operator("m3.forces_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.forces_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_force_index
        if currentIndex >= 0:
            force = scene.m3_forces[currentIndex]
            layout.prop(force, "name", text="Name")
            col = layout.column(align=True)
            row = col.row(align=True)
            row.label(text="Type:")
            row.prop(force, "type", text="")
            row.prop(force, "shape", text="")
            box = col.box()
            brow = box.row(align=True)
            if force.shape == shared.forceShapeSphere:
                brow.prop(force, "width", text="Radius")
            elif force.shape == shared.forceShapeCylinder:
                brow.prop(force, "width", text="Radius")
                brow.prop(force, "height", text="Height")
            elif force.shape == shared.forceShapeBox:
                brow.prop(force, "width", text="Width")
                brow.prop(force, "height", text="Height")
                brow.prop(force, "length", text="Length")
            elif force.shape == shared.forceShapeHemisphere:
                brow.prop(force, "width", text="Radius")
            elif force.shape == shared.forceShapeConeDome:
                brow.prop(force, "width", text="Radius")
                brow.prop(force, "height", text="Cone Ratio")
            layout.prop(force, "strength", text="Strength")
            layout.prop(force, "channels", text="Channels")
            layout.label(text="Flags:")
            box = layout.box()
            row = box.row()
            row.prop(force, "useFalloff", text="Fall Off")
            row.prop(force, "useHeightGradient", text="Height Gradient")
            row.prop(force, "unbounded", text="Unbounded")


class RigidBodyPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_rigid_bodies"
    bl_label = "M3 Rigid Bodies"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        rows = 2
        if len(scene.m3_rigid_bodies) == 1:
            rows = 3
        if len(scene.m3_rigid_bodies) > 1:
            rows = 5

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_rigid_bodies", scene, "m3_rigid_bodies", scene, "m3_rigid_body_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.rigid_bodies_add", icon="ADD", text="")
        col.operator("m3.rigid_bodies_remove", icon="REMOVE", text="")

        if len(scene.m3_rigid_bodies) > 0:
            col.separator()
            col.menu("OBJECT_MT_M3_rigid_bodies", icon="DOWNARROW_HLT", text="")

        if len(scene.m3_rigid_bodies) > 1:
            col.separator()
            col.operator("m3.rigid_bodies_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.rigid_bodies_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_rigid_body_index
        if currentIndex < 0:
            return
        rigid_body = scene.m3_rigid_bodies[currentIndex]

        layout.prop(rigid_body, "name", text="Bone Name")

        # TODO: Bone selection from list would be ideal.
        # This is almost correct, but bpy.data contains deleted items too. :(
        # if bpy.data.armatures:
        #     sub.prop_search(rigid_body, "armatureName", bpy.data, "armatures", text="Armature")
        #     if rigid_body.armatureName and bpy.data.armatures[rigid_body.armatureName]:
        #         sub.prop_search(rigid_body, "boneName", bpy.data.armatures[rigid_body.armatureName], "bones", text="Bone")


class RigidBodyPropertiesPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_rigid_bodies_props"
    bl_label = "Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_rigid_bodies"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_rigid_body_index >= 0

    def draw(self, context):
        scene = context.scene
        rigid_body = scene.m3_rigid_bodies[scene.m3_rigid_body_index]

        layout = self.layout
        col = layout.column_flow(columns=2)
        col.prop(rigid_body, "simulationType", text="Simulation Type")
        col.prop(rigid_body, "physicalMaterial", text="Physical Material")
        col.prop(rigid_body, "density", text="Density")
        col.prop(rigid_body, "friction", text="Friction")
        col.prop(rigid_body, "restitution", text="Restitution")
        col.prop(rigid_body, "gravityScale", text="Gravity Scale")
        col = layout.column(align=True)
        col.prop(rigid_body, "linearDamp", text="Linear Dampening")
        col.prop(rigid_body, "angularDamp", text="Angular Dampening")
        col = layout.column()
        col.prop(rigid_body, "priority", text="Priority")


class RigidBodyForcesPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_rigid_bodies_forces"
    bl_label = "Forces"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_rigid_bodies"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_rigid_body_index >= 0

    def draw(self, context):
        scene = context.scene
        rigid_body = scene.m3_rigid_bodies[scene.m3_rigid_body_index]

        layout = self.layout
        layout.prop(rigid_body, "localForces", text="Local Forces")
        layout.label(text="World Forces:")
        col = layout.column_flow(columns=3)
        col.prop(rigid_body, "wind", text="Wind")
        col.prop(rigid_body, "explosion", text="Explosion")
        col.prop(rigid_body, "energy", text="Energy")
        col.prop(rigid_body, "blood", text="Blood")
        col.prop(rigid_body, "magnetic", text="Magnetic")
        col.prop(rigid_body, "grass", text="Grass")
        col.prop(rigid_body, "brush", text="Brush")
        col.prop(rigid_body, "trees", text="Trees")


class RigidBodyFlagsPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_rigid_bodies_flags"
    bl_label = "Flags"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_rigid_bodies"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_rigid_body_index >= 0

    def draw(self, context):
        scene = context.scene
        rigid_body = scene.m3_rigid_bodies[scene.m3_rigid_body_index]

        layout = self.layout
        col = layout.column_flow(columns=2)
        col.prop(rigid_body, "collidable", text="Collidable")
        col.prop(rigid_body, "walkable", text="Walkable")
        col.prop(rigid_body, "stackable", text="Stackable")
        col.prop(rigid_body, "simulateOnCollision", text="Simulate On Collision")
        col.prop(rigid_body, "ignoreLocalBodies", text="Ignore Local Bodies")
        col.prop(rigid_body, "alwaysExists", text="Always Exists")
        col.prop(rigid_body, "doNotSimulate", text="Do Not Simulate")


class PhysicsShapePanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_physics_shapes"
    bl_label = "Physics Shapes"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "OBJECT_PT_M3_rigid_bodies"

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.m3_rigid_body_index >= 0 and len(context.scene.m3_rigid_bodies)

    def draw(self, context):
        scene = context.scene
        rigid_body = scene.m3_rigid_bodies[scene.m3_rigid_body_index]

        rows = 2
        if len(rigid_body.physicsShapes) > 1:
            rows = 4

        layout = self.layout
        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_physics_sahpes", rigid_body, "physicsShapes", rigid_body, "physicsShapeIndex", rows=rows)
        col = row.column(align=True)
        col.operator("m3.physics_shapes_add", icon="ADD", text="")
        col.operator("m3.physics_shapes_remove", icon="REMOVE", text="")

        if len(rigid_body.physicsShapes) > 1:
            col.separator()
            col.operator("m3.physics_shapes_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.physics_shapes_move", icon="TRIA_DOWN", text="").shift = 1

        if len(rigid_body.physicsShapes) > 0:
            currentIndex = rigid_body.physicsShapeIndex
            physics_shape = rigid_body.physicsShapes[currentIndex]

            layout.prop(physics_shape, "name", text="Name")

            addUIForShapeProperties(layout, physics_shape)


class PhysicsMeshPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_physics_mesh"
    bl_label = "M3 Physics Mesh"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        o = context.object
        return o and (o.data is not None) and (o.type == "MESH")

    def draw(self, context):
        layout = self.layout
        mesh = context.object.data
        layout.prop(mesh, "m3_physics_mesh", text="Physics Mesh Only")


class VisbilityTestPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_visibility_test"
    bl_label = "M3 Visibility Test"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.prop(scene.m3_visibility_test, "radius", text="Radius")
        layout.prop(scene.m3_visibility_test, "center", text="Center")
        layout.prop(scene.m3_visibility_test, "size", text="Size")


class LightPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_lights"
    bl_label = "M3 Lights"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        lights = len(scene.m3_lights)

        rows = 2
        if lights == 1:
            rows = 3
        if lights > 1:
            rows = 5

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_lights", scene, "m3_lights", scene, "m3_light_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.lights_add", icon="ADD", text="")
        col.operator("m3.lights_remove", icon="REMOVE", text="")

        if lights > 0:
            col.separator()
            col.menu("OBJECT_MT_M3_lights", icon="DOWNARROW_HLT", text="")

        if lights > 1:
            col.separator()
            col.operator("m3.lights_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.lights_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_light_index
        if currentIndex >= 0:
            light = scene.m3_lights[currentIndex]
            layout.prop(light, "name", text="Name")
            col = layout.column(align=True)
            col.prop(light, "lightType", text="Light Type")
            box = col.box()
            col = box.column(align=True)
            row = col.row(align=True)
            row.prop(light, "attenuationNear", text="Attenuation Near")
            row.prop(light, "attenuationFar", text="Attenuation Far")
            col.prop(light, "unknownAt148")
            if light.lightType == shared.lightTypeSpot:
                row = col.row(align=True)
                row.prop(light, "hotSpot", text="Hot Spot")
                row.prop(light, "falloff", text="Fall Off")
            row = layout.row()
            col = row.column()
            col.label(text="")
            col.label(text="Color:")
            col.label(text="Intensity:")
            col = row.column(align=True)
            col.label(text="")
            col.prop(light, "lightColor", text="")
            col.prop(light, "lightIntensity", text="")
            col = row.column()
            col.prop(light, "specular", text="Specular:")
            sub = col.column(align=True)
            sub.active = light.specular
            sub.prop(light, "specColor", text="")
            sub.prop(light, "specIntensity", text="")
            box = layout.box()
            col = box.column_flow(columns=2)
            col.prop(light, "shadowCast", text="Shadow Cast")
            col.prop(light, "affectedByAO")
            col.prop(light, "lightOpaqueObjects", text="Light opaque objects")
            col.prop(light, "lightTransparentObjects", text="Light transparent objects")
            col.prop(light, "useTeamColor")
            row = layout.row()
            row.label(text="LOD Cut/Shadow LOD Cut:")
            row.prop(light, "lodCut", text="")
            row.prop(light, "shadowLodCut", text="")


class BillboardBehaviorPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_billboard_behavior"
    bl_label = "M3 Billboard Behaviors"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        billboards = len(scene.m3_billboard_behaviors)

        rows = 2
        if billboards > 1:
            rows = 4

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_billboard_behaviors", scene, "m3_billboard_behaviors", scene, "m3_billboard_behavior_index", rows=rows)
        col = row.column(align=True)
        col.operator("m3.billboard_behaviors_add", icon="ADD", text="")
        col.operator("m3.billboard_behaviors_remove", icon="REMOVE", text="")

        if billboards > 1:
            col.separator()
            col.operator("m3.billboard_behaviors_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.billboard_behaviors_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_billboard_behavior_index
        if currentIndex >= 0:
            billboardBehavior = scene.m3_billboard_behaviors[currentIndex]
            layout.separator()
            layout.prop(billboardBehavior, "name", text="Bone Name")
            layout.prop(billboardBehavior, "billboardType", text="Billboard Type")


class InverseKinematicChainPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_ik_chain"
    bl_label = "M3 Inverse Kinematic Chains"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        iks = len(scene.m3_ik_chains)

        rows = 2
        if iks > 1:
            rows = 4

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_ik_chains", scene, "m3_ik_chains", scene, "m3_ik_chain_index", rows=rows)
        col = row.column(align=True)
        col.operator("m3.ik_chains_add", icon="ADD", text="")
        col.operator("m3.ik_chains_remove", icon="REMOVE", text="")

        if iks > 1:
            col.separator()
            col.operator("m3.ik_chains_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.ik_chains_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_ik_chain_index
        if currentIndex >= 0:
            ik = scene.m3_ik_chains[currentIndex]
            layout.separator()
            layout.prop(ik, "name", text="Chain Name")
            col = layout.column(align=True)
            col.prop(ik, "boneName1", text="Bone Base")
            col.prop(ik, "boneName2", text="Bone Foot")
            col = layout.column(align=True)
            col.prop(ik, "maxSearchUp", text="Max Search Up")
            col.prop(ik, "maxSearchDown", text="Max Search Down")
            col.prop(ik, "maxSpeed", text="Max Search Speed")
            col.prop(ik, "goalPosThreshold", text="Goal Position Threshold")


class TurretBehaviorPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_turret_behavior"
    bl_label = "M3 Turret Behaviors"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        turrets = len(scene.m3_turret_behaviors)

        rows = 2
        if turrets > 1:
            rows = 4

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_turret_behaviors", scene, "m3_turret_behaviors", scene, "m3_turret_behavior_index", rows=rows)
        col = row.column(align=True)
        col.operator("m3.turret_behaviors_add", icon="ADD", text="")
        col.operator("m3.turret_behaviors_remove", icon="REMOVE", text="")

        if turrets > 1:
            col.separator()
            col.operator("m3.turret_behaviors_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.turret_behaviors_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_turret_behavior_index
        if currentIndex >= 0:
            turret = scene.m3_turret_behaviors[currentIndex]
            layout.separator()
            layout.prop(turret, "name", text="Turret ID")
            turret = scene.m3_turret_behaviors[currentIndex]
            parts = len(turret.parts)

            rows = 2
            if parts > 1:
                rows = 4

            row = layout.row()
            col = row.column()
            col.template_list("UI_UL_list", "parts", turret, "parts", turret, "part_index", rows=rows)
            col = row.column(align=True)
            col.operator("m3.turret_behavior_parts_add", icon="ADD", text="")
            col.operator("m3.turret_behavior_parts_remove", icon="REMOVE", text="")

            if parts > 1:
                col.separator()
                col.operator("m3.turret_behavior_parts_move", icon="TRIA_UP", text="").shift = -1
                col.operator("m3.turret_behavior_parts_move", icon="TRIA_DOWN", text="").shift = 1

            if turret.part_index >= 0:
                part = turret.parts[turret.part_index]
                col = layout.column(align=True)
                col.prop(part, "name", text="Bone Name")
                col.prop(part, "mainTurretBone", text="Main Turret Bone")
                col.prop(part, "groupId", text="Turret group ID")
                row = layout.row()
                col = row.column(align=True)
                col.prop(part, "forwardX", text="Forward Vector X")
                col = row.column(align=True)
                col.prop(part, "forwardY", text="Y")
                col = row.column(align=True)
                col.prop(part, "forwardZ", text="Z")
                row = layout.row()
                col = row.column(align=True)
                col.prop(part, "upX", text="Upward Vector X")
                col = row.column(align=True)
                col.prop(part, "upY", text="Y")
                col = row.column(align=True)
                col.prop(part, "upZ", text="Z")
                row = layout.row()
                col = row.column(align=True)
                col.prop(part, "yawWeight", text="Yaw Weight")
                col.prop(part, "yawLimited", text="Limited")
                sub = col.column(align=True)
                sub.active = part.yawLimited
                sub.prop(part, "yawMin", text="Minimum")
                sub.prop(part, "yawMax", text="Maximum")
                col = row.column(align=True)
                col.prop(part, "pitchWeight", text="Pitch Weight")
                col.prop(part, "pitchLimited", text="Limited")
                sub = col.column(align=True)
                sub.active = part.pitchLimited
                sub.prop(part, "pitchMin", text="Minimum")
                sub.prop(part, "pitchMax", text="Maximum")
                col = layout.column(align=True)
                col.prop(part, "unknownAt132")
                col.prop(part, "unknownAt136")
                col.prop(part, "unknownAt140")
                col.prop(part, "unknownAt144")
                col.prop(part, "unknownAt148")


class PhysicsJointPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_physics_joint"
    bl_label = "M3 Physics Joints"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        joints = len(scene.m3_physics_joints)

        rows = 2
        if joints > 1:
            rows = 4

        layout.prop(scene, "m3_physics_joint_pivots", text="Display Physics Joint Pivot Helpers")
        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_physics_joints", scene, "m3_physics_joints", scene, "m3_physics_joint_index", rows=rows)
        col = row.column(align=True)
        col.operator("m3.physics_joints_add", icon="ADD", text="")
        col.operator("m3.physics_joints_remove", icon="REMOVE", text="")

        if joints > 1:
            col.separator()
            col.operator("m3.physics_joints_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.physics_joints_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_physics_joint_index
        if currentIndex < 0:
            return

        joint = scene.m3_physics_joints[scene.m3_physics_joint_index]

        col = layout.column()
        col.prop(joint, "name", text="Joint ID")
        col.prop(joint, "boneName1", text="Bone 1")
        col.prop(joint, "boneName2", text="Bone 2")
        col = layout.column(align=True)
        col.prop(joint, "jointType", text="Joint Type")
        box = col.box()

        if joint.jointType != shared.physicsJointWeld:

            if joint.jointType == shared.physicsJointCone:
                box.prop(joint, "coneAngle", text="Cone Angle")

            if joint.jointType in [shared.physicsJointRevolute, shared.physicsJointCone]:
                brow = box.row()
                brow.prop(joint, "limit", text="Limit Rotation")
                sub = brow.column(align=True)
                sub.active = joint.limit
                sub.prop(joint, "limitMin", text="Minimum")
                sub.prop(joint, "limitMax", text="Maximim")

            brow = box.row()
            brow.prop(joint, "friction", text="Joint Friction")
            sub = brow.column()
            sub.active = joint.friction
            sub.prop(joint, "frictionAmount", text="")

        else:
            brow = box.row()
            brow.prop(joint, "angularFrequency", text="Angular Frequency")
            brow.prop(joint, "dampingRatio", text="Damping Ratio")

        col = layout.column()
        col.label(text="Bone 1 Joint:")
        row = col.row()
        sub = row.column()
        sub.prop(joint, "offset1", text="Location")
        sub = row.column()
        sub.prop(joint, "rotation1", text="Rotation")
        col = layout.column()
        col.label(text="Bone 2 Joint:")
        row = col.row()
        sub = row.column()
        sub.prop(joint, "offset2", text="Location")
        sub = row.column()
        sub.prop(joint, "rotation2", text="Rotation")
        col = layout.column()
        col.prop(joint, "shapeCollisionValue")


class WarpPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_warps"
    bl_label = "M3 Warp Fields"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        warps = len(scene.m3_warps)

        rows = 2
        if warps == 1:
            rows = 3
        if warps > 1:
            rows = 5

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_warps", scene, "m3_warps", scene, "m3_warp_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.warps_add", icon="ADD", text="")
        col.operator("m3.warps_remove", icon="REMOVE", text="")

        if warps > 0:
            col.separator()
            col.menu("OBJECT_MT_M3_warps", icon="DOWNARROW_HLT", text="")

        if warps > 1:
            col.separator()
            col.operator("m3.warps_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.warps_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_warp_index
        if currentIndex >= 0:
            warp = scene.m3_warps[currentIndex]
            col = layout.column(align=True)
            col.prop(warp, "name", text="Name")
            col.prop(warp, "radius", text="Radius")
            col.prop(warp, "unknown9306aac0", text="Unk. 9306aac0")
            col.prop(warp, "compressionStrength", text="Compression Strength")
            col.prop(warp, "unknown50c7f2b4", text="Unk. 50c7f2b4")
            col.prop(warp, "unknown8d9c977c", text="Unk. 8d9c977c")
            col.prop(warp, "unknownca6025a2", text="Unk. ca6025a2")


class AttachmentPointsPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_attachments"
    bl_label = "M3 Attachment Points"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        attachPoint = scene.m3_attachment_point_index
        attachPoints = len(scene.m3_attachment_points)

        rows = 2
        if attachPoints > 1:
            rows = 4

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_attachment_points", scene, "m3_attachment_points", scene, "m3_attachment_point_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.attachment_points_add", icon="ADD", text="")
        col.operator("m3.attachment_points_remove", icon="REMOVE", text="")
        if attachPoints > 1:
            col.separator()
            col.operator("m3.attachment_points_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.attachment_points_move", icon="TRIA_DOWN", text="").shift = 1

        if attachPoint >= 0 and attachPoint < attachPoints:
            attachment_point = scene.m3_attachment_points[attachPoint]
            layout.prop(attachment_point, "name", text="Name")
            col = layout.column(align=True)
            col.prop(attachment_point, "volumeType", text="Volume")
            if attachment_point.volumeType in ["0", "1", "2"]:
                box = col.box()
                bcol = box.column(align=True)
                if attachment_point.volumeType in ["1", "2"]:
                    bcol.prop(attachment_point, "volumeSize0", text="Volume Radius")
                elif attachment_point.volumeType in ["0"]:
                    bcol.prop(attachment_point, "volumeSize0", text="Volume Width")
                if attachment_point.volumeType in ["0"]:
                    bcol.prop(attachment_point, "volumeSize1", text="Volume Length")
                elif attachment_point.volumeType in ["2"]:
                    bcol.prop(attachment_point, "volumeSize1", text="Volume Height")
                if attachment_point.volumeType in ["0"]:
                    bcol.prop(attachment_point, "volumeSize2", text="Volume Height")


def addUIForShapeProperties(layout, shapeObject):
    col = layout.column(align=True)
    col.prop(shapeObject, "shape", text="Shape")
    box = col.box()
    row = box.row()
    if shapeObject.shape in ["0", "1", "2", "3"]:
        col = row.column(align=True)
        col.label(text="Dimensions:")
        if shapeObject.shape in ["0"]:  # cuboid
            col.prop(shapeObject, "size0", text="X")
            col.prop(shapeObject, "size1", text="Y")
            col.prop(shapeObject, "size2", text="Z")
        elif shapeObject.shape in ["1"]:  # sphere
            col.prop(shapeObject, "size0", text="R")
        elif shapeObject.shape in ["2"]:  # capsule
            col.prop(shapeObject, "size0", text="R")
            col.prop(shapeObject, "size1", text="H")
        elif shapeObject.shape in ["3"]:  # cylinder
            col.prop(shapeObject, "size0", text="R")
            col.prop(shapeObject, "size1", text="H")
    elif shapeObject.shape in ["4", "5"]:
        box.prop(shapeObject, "meshObjectName", text="Mesh Name")

    row = box.row()
    col = row.column(align=True)
    col.label(text="Offset:")
    col.prop(shapeObject, "offset", index=0, text="X")
    col.prop(shapeObject, "offset", index=1, text="Y")
    col.prop(shapeObject, "offset", index=2, text="Z")
    col = row.column(align=True)
    col.label(text="Rotation:")
    col.prop(shapeObject, "rotationEuler", index=0, text="X")
    col.prop(shapeObject, "rotationEuler", index=1, text="Y")
    col.prop(shapeObject, "rotationEuler", index=2, text="Z")
    col = row.column(align=True)
    col.label(text="Scale:")
    col.prop(shapeObject, "scale", index=0, text="X")
    col.prop(shapeObject, "scale", index=1, text="Y")
    col.prop(shapeObject, "scale", index=2, text="Z")


class FuzzyHitTestPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_fuzzyhittests"
    bl_label = "M3 Fuzzy Hit Tests"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        rows = 2
        if len(scene.m3_fuzzy_hit_tests) > 1:
            rows = 4

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "m3_fuzzy_hit_tests", scene, "m3_fuzzy_hit_tests", scene, "m3_fuzzy_hit_test_index", rows=rows)

        col = row.column(align=True)
        col.operator("m3.fuzzy_hit_tests_add", icon="ADD", text="")
        col.operator("m3.fuzzy_hit_tests_remove", icon="REMOVE", text="")

        if len(scene.m3_fuzzy_hit_tests) > 1:
            col.separator()
            col.operator("m3.fuzzy_hit_tests_move", icon="TRIA_UP", text="").shift = -1
            col.operator("m3.fuzzy_hit_tests_move", icon="TRIA_DOWN", text="").shift = 1

        currentIndex = scene.m3_fuzzy_hit_test_index
        if currentIndex >= 0 and currentIndex < len(scene.m3_fuzzy_hit_tests):
            fuzzy_hit_test = scene.m3_fuzzy_hit_tests[currentIndex]
            layout.separator()
            addUIForShapeProperties(layout, fuzzy_hit_test)


class TightHitTestPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_tighthittest"
    bl_label = "M3 Tight Hit Test"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        if scene.m3_tight_hit_test.name == "":
            layout.operator("m3.tight_hit_test_select_or_create_bone", text="Create Bone")
        else:
            layout.operator("m3.tight_hit_test_select_or_create_bone", text="Select Bone")
            layout.operator("m3.tight_hit_test_remove", text="Remove Tight Hit Test")
        split = layout.split()
        row = split.row()
        sub = row.column(align=False)
        sub.active = scene.m3_tight_hit_test.name != ""
        addUIForShapeProperties(sub, scene.m3_tight_hit_test)


class ExtraBonePropertiesPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_bone_properties"
    bl_label = "M3 Bone Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "bone"

    @classmethod
    def poll(cls, context):
        return context.bone

    def draw(self, context):
        layout = self.layout
        bone = context.bone
        layout.prop(bone, "m3_bind_scale", text="Bind Scale")


class M3_MATERIALS_OT_add(bpy.types.Operator):
    bl_idname = "m3.materials_add"
    bl_label = "Add M3 Material"
    bl_description = "Adds an material for the export to Starcraft 2"
    bl_options = {"UNDO"}

    defaultSetting: bpy.props.EnumProperty(items=matDefaultSettingsList, default="MESH")
    materialName: bpy.props.StringProperty(name="materialName", default="01")

    def invoke(self, context, event):
        scene = context.scene
        self.materialName = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_material_references])
        context.window_manager.invoke_props_dialog(self, width=250)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "defaultSetting", text="Default Settings")
        layout.prop(self, "materialName", text="Name")

    def execute(self, context):
        scene = context.scene
        createMaterial(scene, self.materialName, self.defaultSetting)
        return {"FINISHED"}


class M3_MATERIALS_OT_createForMesh(bpy.types.Operator):
    bl_idname = "m3.create_material_for_mesh"
    bl_label = "Creates a M3 Material for the current mesh"
    bl_description = "Creates an m3 material for the current mesh"
    bl_options = {"UNDO"}

    defaultSetting: bpy.props.EnumProperty(items=matDefaultSettingsList, default="MESH")
    materialName: bpy.props.StringProperty(name="materialName", default="01")

    def invoke(self, context, event):
        scene = context.scene
        self.materialName = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_material_references])
        context.window_manager.invoke_props_dialog(self, width=250)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "defaultSetting", text="Default Settings")
        layout.prop(self, "materialName", text="Name")

    def execute(self, context):
        scene = context.scene
        meshObject = context.object
        mesh = meshObject.data
        createMaterial(scene, self.materialName, self.defaultSetting)
        mesh.m3_material_name = self.materialName

        return {"FINISHED"}


class M3_MATERIALS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.materials_remove"
    bl_label = "Remove M3 Material"
    bl_description = "Removes the active M3 Material"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        referenceIndex = scene.m3_material_reference_index
        if referenceIndex >= 0:
            materialReference = scene.m3_material_references[referenceIndex]
            materialName = materialReference.name
            # Check if material is in use, and abort:
            for particle_system in scene.m3_particle_systems:
                if particle_system.materialName == materialName:
                    self.report({"ERROR"}, "Can't delete: The particle system \"%s\" is using this material" % particle_system.name)
                    return {"CANCELLED"}
            for ribbon in scene.m3_ribbons:
                if ribbon.materialName == materialName:
                    self.report({"ERROR"}, "Can't delete: The ribbon \"%s\" is using this material" % ribbon.name)
                    return {"CANCELLED"}
            for projection in scene.m3_projections:
                if projection.materialName == materialName:
                    self.report({"ERROR"}, "Can't delete: The projection \"%s\" is using this material" % projection.name)
                    return {"CANCELLED"}
            for meshObject in shared.findMeshObjects(scene):
                mesh = meshObject.data
                if mesh.m3_material_name == materialName:
                    self.report({"ERROR"}, "Can't delete: The object \"%s\" (mesh \"%s\") is using this material." % (meshObject.name, mesh.name))
                    return {"CANCELLED"}

            for higherReferenceIndex in range(referenceIndex + 1, len(scene.m3_material_references)):
                higherReference = scene.m3_material_references[higherReferenceIndex]
                material = cm.getMaterial(scene, higherReference.materialType, higherReference.materialIndex)
                if material is not None:
                    material.materialReferenceIndex -= 1

            materialReference = scene.m3_material_references[referenceIndex]
            materialIndex = materialReference.materialIndex
            materialType = materialReference.materialType

            for otherReference in scene.m3_material_references:
                if otherReference.materialType == materialType and otherReference.materialIndex > materialIndex:
                    otherReference.materialIndex -= 1

            blenderMaterialsFieldName = cm.blenderMaterialsFieldNames[materialType]
            blenderMaterialsField = getattr(scene, blenderMaterialsFieldName)
            blenderMaterialsField.remove(materialIndex)

            scene.m3_material_references.remove(scene.m3_material_reference_index)
            scene.m3_material_reference_index -= 1
        return {"FINISHED"}


class M3_MATERIALS_OT_move(bpy.types.Operator):
    bl_idname = "m3.materials_move"
    bl_label = "Move Material"
    bl_description = "Moves the active M3 material"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_material_reference_index

        if (ii < len(scene.m3_material_references) - self.shift and ii >= -self.shift):
            scene.m3_material_references.move(ii, ii + self.shift)
            scene.m3_material_reference_index += self.shift

        return {"FINISHED"}


class M3_MATERIALS_OT_duplicate(bpy.types.Operator):
    bl_idname = "m3.materials_duplicate"
    bl_label = "Duplicate Material"
    bl_description = "Duplicates the active M3 material"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        matRef = scene.m3_material_references[scene.m3_material_reference_index]
        mat = cm.getMaterial(scene, matRef.materialType, matRef.materialIndex)

        matName = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_material_references], prefix=matRef.name)

        if matRef.materialType == shared.standardMaterialTypeIndex:
            createMaterial(scene, matName, defaultSettingMesh)

        elif matRef.materialType == shared.displacementMaterialTypeIndex:
            createMaterial(scene, matName, defaultSettingDisplacement)

        elif matRef.materialType == shared.compositeMaterialTypeIndex:
            createMaterial(scene, matName, defaultSettingComposite)

        elif matRef.materialType == shared.terrainMaterialTypeIndex:
            createMaterial(scene, matName, defaultSettingTerrain)

        elif matRef.materialType == shared.volumeMaterialTypeIndex:
            createMaterial(scene, matName, defaultSettingVolume)

        elif matRef.materialType == shared.volumeNoiseMaterialTypeIndex:
            createMaterial(scene, matName, defaultSettingVolume)

        elif matRef.materialType == shared.CreepMaterialTypeIndex:
            createMaterial(scene, matName, defaultSettingCreep)

        elif matRef.materialType == shared.stbNoiseMaterialTypeIndex:
            createMaterial(scene, matName, defaultSettingSplatTerrainBake)

        elif matRef.materialType == shared.lensFlareNoiseMaterialTypeIndex:
            createMaterial(scene, matName, defaultSettingLensFlare)

        newMatRef = scene.m3_material_references[scene.m3_material_reference_index]
        newMat = cm.getMaterial(scene, newMatRef.materialType, newMatRef.materialIndex)
        shared.copyBpyProps(newMat, mat, skip=["name", "layers", "sections", "materialReferenceIndex"])

        if hasattr(mat, "layers"):
            for layer, newLayer in zip(mat.layers, newMat.layers):
                shared.copyBpyProps(newLayer, layer)

                a = len(mat.layers) - 1
                b = len(newMat.layers) - 1
                while a < b:
                    newMat.layers.remove(b)
                    b -= 1

        if hasattr(mat, "sections"):
            for section in mat.sections:
                newSection = newMat.sections.add()
                shared.copyBpyProps(newSection, section)

        return {"FINISHED"}


class M3_COMPOSITE_MATERIAL_OT_add_section(bpy.types.Operator):
    bl_idname = "m3.composite_material_add_section"
    bl_label = "Add Section"
    bl_description = "Adds a section/layer to the composite material"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        materialIndex = scene.m3_material_reference_index
        if materialIndex >= 0 and materialIndex < len(scene.m3_material_references):
            materialReference = scene.m3_material_references[materialIndex]
            materialType = materialReference.materialType
            materialIndex = materialReference.materialIndex
            if materialType == shared.compositeMaterialTypeIndex:
                material = cm.getMaterial(scene, materialType, materialIndex)
                section = material.sections.add()
                if len(scene.m3_material_references) >= 1:
                    section.name = scene.m3_material_references[0].name
                material.sectionIndex = len(material.sections) - 1
        return {"FINISHED"}


class M3_COMPOSITE_MATERIAL_OT_remove_section(bpy.types.Operator):
    bl_idname = "m3.composite_material_remove_section"
    bl_label = "Removes Section"
    bl_description = "Removes the selected section/layer from the composite material"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        materialIndex = scene.m3_material_reference_index
        if materialIndex >= 0 and materialIndex < len(scene.m3_material_references):
            materialReference = scene.m3_material_references[materialIndex]
            materialType = materialReference.materialType
            materialIndex = materialReference.materialIndex
            if materialType == shared.compositeMaterialTypeIndex:
                material = cm.getMaterial(scene, materialType, materialIndex)
                sectionIndex = material.sectionIndex
                if (sectionIndex >= 0) and (sectionIndex < len(material.sections)):
                    material.sections.remove(sectionIndex)
                    material.sectionIndex = material.sectionIndex - 1
        return {"FINISHED"}


class M3_COMPOSITE_MATERIAL_OT_move_section(bpy.types.Operator):
    bl_idname = "m3.composite_material_move_section"
    bl_label = "Move section"
    bl_description = "Moves the active section of the composite material"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        matRef = scene.m3_material_references[scene.m3_material_reference_index]

        if matRef.materialType == shared.compositeMaterialTypeIndex:
            mat = cm.getMaterial(scene, matRef.materialType, matRef.materialIndex)
            ii = mat.sectionIndex

            if (ii < len(mat.sections) - self.shift and ii >= -self.shift):
                mat.sections.move(ii, ii + self.shift)
                mat.sectionIndex += self.shift

        return {"FINISHED"}


class M3_ANIMATIONS_OT_add(bpy.types.Operator):
    bl_idname = "m3.animations_add"
    bl_label = "Add Animation Sequence"
    bl_description = "Adds an animation sequence for the export to Starcraft 2"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        animation = scene.m3_animations.add()
        name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_animations], suggestedNames=["Birth", "Stand", "Death", "Walk", "Attack"], prefix="Stand")

        bpy.data.actions.new("Armature Object" + name)
        bpy.data.actions.new("Scene" + name)

        animation.nameOld = name
        animation.name = animation.nameOld
        animation.startFrame = 0
        animation.exlusiveEndFrame = 60
        animation.frequency = 1
        animation.movementSpeed = 0

        scene.m3_animation_index = len(scene.m3_animations) - 1
        return {"FINISHED"}


class M3_ANIMATIONS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.animations_remove"
    bl_label = "Remove Animation Sequence"
    bl_description = "Removes the active M3 animation sequence"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if len(scene.m3_animations) > 0:
            animation = scene.m3_animations[scene.m3_animation_index]

            armAction = bpy.data.actions["Armature Object" + animation.name] if "Armature Object" + animation.name in bpy.data.actions else None
            scnAction = bpy.data.actions["Scene" + animation.name] if "Scene" + animation.name in bpy.data.actions else None

            if armAction:
                armAction.name = armAction.name + "(Deleted)"
                armAction.use_fake_user = False
            if scnAction:
                scnAction.name = scnAction.name + "(Deleted)"
                scnAction.use_fake_user = False

            scene.m3_animations.remove(scene.m3_animation_index)

            # Here we jog the animation index to make sure actions get refreshed
            scene.m3_animation_index -= 1 if scene.m3_animation_index > 0 or len(scene.m3_animations) == 0 else 0
            scene.m3_animation_index += 1 if scene.m3_animation_index is len(scene.m3_animations) else 0

        return {"FINISHED"}


class M3_ANIMATIONS_OT_move(bpy.types.Operator):
    bl_idname = "m3.animations_move"
    bl_label = "Move Animation Sequence"
    bl_description = "Moves the active M3 animation sequence"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_animation_index

        if (ii < len(scene.m3_animations) - self.shift):
            scene.m3_animations.move(ii, ii + self.shift)
            scene.m3_animation_index += self.shift

        return {"FINISHED"}


def copyCurrentActionOfObjectToM3Animation(scene, targetAnimation):
    sourceArmAction = bpy.data.actions.get('Armature Object' + scene.m3_animations[scene.m3_animation_index].name)
    sourceScnAction = bpy.data.actions.get('Scene' + scene.m3_animations[scene.m3_animation_index].name)

    newArmAction = bpy.data.actions.new('Armature Object' + targetAnimation.name)
    newScnAction = bpy.data.actions.new('Scene' + targetAnimation.name)

    for sourceAction, targetAction in [sourceArmAction, newArmAction], [sourceScnAction, newScnAction]:
        for sourceCurve in sourceAction.fcurves:
            path = sourceCurve.data_path
            arrayIndex = sourceCurve.array_index
            if sourceCurve.group is not None:
                groupName = sourceCurve.group.name
                targetCurve = targetAction.fcurves.new(path, index=arrayIndex, action_group=groupName)
            else:
                targetCurve = targetAction.fcurves.new(path, index=arrayIndex)
            targetCurve.extrapolation = sourceCurve.extrapolation
            targetCurve.color_mode = sourceCurve.color_mode
            targetCurve.color = sourceCurve.color
            for sourceKeyFrame in sourceCurve.keyframe_points:
                frame = sourceKeyFrame.co.x
                value = sourceKeyFrame.co.y
                targetKeyFrame = targetCurve.keyframe_points.insert(frame, value)
                targetKeyFrame.handle_left_type = sourceKeyFrame.handle_left_type
                targetKeyFrame.handle_right_type = sourceKeyFrame.handle_right_type
                targetKeyFrame.interpolation = sourceKeyFrame.interpolation
                targetKeyFrame.type = sourceKeyFrame.type
                targetKeyFrame.handle_left.x = sourceKeyFrame.handle_left.x
                targetKeyFrame.handle_left.y = sourceKeyFrame.handle_left.y
                targetKeyFrame.handle_right.x = sourceKeyFrame.handle_right.x
                targetKeyFrame.handle_right.y = sourceKeyFrame.handle_right.y


class M3_ANIMATIONS_OT_duplicate(bpy.types.Operator):
    bl_idname = "m3.animations_duplicate"
    bl_label = "Copy Animation"
    bl_description = "Create identical copy of the animation"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        animation = scene.m3_animations[scene.m3_animation_index]

        uniqueNameFinder = shared.UniqueNameFinder()
        uniqueNameFinder.markNamesOfCollectionAsUsed(scene.m3_animations)

        newAnimation = scene.m3_animations.add()

        shared.copyBpyProps(newAnimation, animation, skip=["nameOld", "name", "transformationCollections"])

        newAnimation.nameOld = uniqueNameFinder.findNameAndMarkAsUsedLike(animation.name)
        newAnimation.name = newAnimation.nameOld

        for stc in animation.transformationCollections:
            newStc = newAnimation.transformationCollections.add()

            shared.copyBpyProps(newStc, stc, skip=["animatedProperties"])

            for animProp in stc.animatedProperties:
                newAnimProp = newStc.animatedProperties.add()

                shared.copyBpyProps(newAnimProp, animProp)

        copyCurrentActionOfObjectToM3Animation(scene, newAnimation)

        scene.m3_animation_index = len(scene.m3_animations) - 1

        return {"FINISHED"}


class M3_ANIMATIONS_OT_deselect(bpy.types.Operator):
    bl_idname = "m3.animations_deselect"
    bl_label = "Edit Default Values"
    bl_description = "Deselects the active M3 animation sequence so that the default values can be edited"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        scene.m3_animation_index = -1
        return {"FINISHED"}


class M3_ANIMATIONS_OT_STC_add(bpy.types.Operator):
    bl_idname = "m3.stc_add"
    bl_label = "Add sub animation"
    bl_description = "Add sub animation to the active animation sequence"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_animation_index >= 0:
            animation = scene.m3_animations[scene.m3_animation_index]
            stcIndex = len(animation.transformationCollections)
            stc = animation.transformationCollections.add()
            stc.name = shared.findUnusedPropItemName(scene, propGroups=[animation.transformationCollections], suggestedNames=["full"], prefix="")
            animation.transformationCollectionIndex = stcIndex

        return {"FINISHED"}


class M3_ANIMATIONS_OT_STC_remove(bpy.types.Operator):
    bl_idname = "m3.stc_remove"
    bl_label = "Remove sub animation from animation"
    bl_description = "Removes the active sub animation from animation sequence"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_animation_index >= 0:
            animation = scene.m3_animations[scene.m3_animation_index]
            stcIndex = animation.transformationCollectionIndex
            if stcIndex >= 0 and stcIndex < len(animation.transformationCollections):
                animation.transformationCollections.remove(stcIndex)
                animation.transformationCollectionIndex -= 1

        return {"FINISHED"}


class M3_ANIMATIONS_OT_STC_move(bpy.types.Operator):
    bl_idname = "m3.stc_move"
    bl_label = "Move sub animation"
    bl_description = "Moves the active sub animation"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        animation = scene.m3_animations[scene.m3_animation_index]
        ii = animation.transformationCollectionIndex

        if (ii < len(animation.transformationCollections) - self.shift and ii >= -self.shift):
            animation.transformationCollections.move(ii, ii + self.shift)
            animation.transformationCollectionIndex += self.shift

        return {"FINISHED"}


class M3_ANIMATIONS_OT_STC_select(bpy.types.Operator):
    bl_idname = "m3.stc_select"
    bl_label = "Select all FCurves of the active sub animation"
    bl_description = "Selects all FCURVES of the active sub animation"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        longAnimIds = set()

        stc = None
        if scene.m3_animation_index >= 0:
            animation = scene.m3_animations[scene.m3_animation_index]
            stcIndex = animation.transformationCollectionIndex
            if stcIndex >= 0 and stcIndex < len(animation.transformationCollections):
                stc = animation.transformationCollections[stcIndex]
        if stc is not None:
            for animatedProperty in stc.animatedProperties:
                longAnimId = animatedProperty.longAnimId
                longAnimIds.add(longAnimId)

        for obj in bpy.data.objects:
            if obj.type == "ARMATURE":
                armature = obj.data
                selectObject = False
                for bone in armature.bones:
                    animPathPrefix = "pose.bones[\"{name}\"].".format(name=bone.name)
                    objectId = shared.animObjectIdArmature
                    rotLongAnimId = shared.getLongAnimIdOf(objectId, animPathPrefix + "rotation_quaternion")
                    locLongAnimId = shared.getLongAnimIdOf(objectId, animPathPrefix + "location")
                    scaleLongAnimId = shared.getLongAnimIdOf(objectId, animPathPrefix + "scale")
                    if (rotLongAnimId in longAnimIds) or (locLongAnimId in longAnimIds) or (scaleLongAnimId in longAnimIds):
                        bone.select = True
                        selectObject = True
                    else:
                        bone.select = False

                obj.select_set(selectObject)
                if obj.animation_data is not None:
                    action = obj.animation_data.action
                    if action is not None:
                        for fcurve in action.fcurves:
                            animPath = fcurve.data_path
                            objectId = shared.animObjectIdArmature
                            longAnimId = shared.getLongAnimIdOf(objectId, animPath)
                            fcurve.select = longAnimId in longAnimIds

        if scene.animation_data is not None:
            action = scene.animation_data.action
            if action is not None:
                for fcurve in action.fcurves:
                    animPath = fcurve.data_path
                    objectId = shared.animObjectIdScene
                    longAnimId = shared.getLongAnimIdOf(objectId, animPath)
                    fcurve.select = longAnimId in longAnimIds

        return {"FINISHED"}


class M3_ANIMATIONS_OT_STC_assign(bpy.types.Operator):
    bl_idname = "m3.stc_assign"
    bl_label = "Assign FCurves to sub animation"
    bl_description = "Assigns all selected FCurves to the active sub animation"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_animation_index < 0:
            return {"FINISHED"}

        selectedLongAnimIds = set(self.getSelectedLongAnimIdsOfCurrentActions(scene))

        animation = scene.m3_animations[scene.m3_animation_index]
        selectedSTCIndex = animation.transformationCollectionIndex

        for stcIndex, stc in enumerate(animation.transformationCollections):
            if stcIndex == selectedSTCIndex:
                stc.animatedProperties.clear()
                for longAnimId in selectedLongAnimIds:
                    animatedProperty = stc.animatedProperties.add()
                    animatedProperty.longAnimId = longAnimId
            else:
                # Remove selected properties from the other STCs:
                longAnimIds = set()
                for animatedProperty in stc.animatedProperties:
                    longAnimIds.add(animatedProperty.longAnimId)
                longAnimIds = longAnimIds - selectedLongAnimIds
                stc.animatedProperties.clear()
                for longAnimId in longAnimIds:
                    animatedProperty = stc.animatedProperties.add()
                    animatedProperty.longAnimId = longAnimId

        return {"FINISHED"}

    def getSelectedAnimationPaths(self, objectWithAnimData):
        if objectWithAnimData.animation_data is not None:
            action = objectWithAnimData.animation_data.action
            if action is not None:
                for fcurve in action.fcurves:
                    if fcurve.select:
                        animPath = fcurve.data_path
                        yield animPath

    def getSelectedLongAnimIdsOfCurrentActions(self, scene):
        for obj in bpy.data.objects:
            if obj.type == "ARMATURE":
                for animPath in self.getSelectedAnimationPaths(obj):
                    yield shared.getLongAnimIdOf(shared.animObjectIdArmature, animPath)
        for animPath in self.getSelectedAnimationPaths(scene):
            yield shared.getLongAnimIdOf(shared.animObjectIdScene, animPath)


class M3_CAMERAS_OT_add(bpy.types.Operator):
    bl_idname = "m3.cameras_add"
    bl_label = "Add M3 Camera"
    bl_description = "Adds a camera description for the export as m3"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        camera = scene.m3_cameras.add()
        camera.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_cameras], suggestedNames=["CameraPortrait", "CameraAvatar"], prefix="Camera")

        # The following selection causes a new bone to be created:
        scene.m3_camera_index = len(scene.m3_cameras) - 1
        return {"FINISHED"}


class M3_CAMERAS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.cameras_remove"
    bl_label = "Remove Camera"
    bl_description = "Removes the active M3 camera"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_camera_index >= 0:
            camera = scene.m3_cameras[scene.m3_camera_index]
            removeBone(scene, camera.name)
            scene.m3_cameras.remove(scene.m3_camera_index)
            if scene.m3_camera_index != 0:
                scene.m3_camera_index -= 1
        return {"FINISHED"}


class M3_CAMERAS_OT_move(bpy.types.Operator):
    bl_idname = "m3.cameras_move"
    bl_label = "Move Camera"
    bl_description = "Moves the active M3 camera"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_camera_index

        if (ii < len(scene.m3_cameras) - self.shift and ii >= -self.shift):
            scene.m3_cameras.move(ii, ii + self.shift)
            scene.m3_camera_index += self.shift

        return {"FINISHED"}


class M3_CAMERAS_OT_duplicate(bpy.types.Operator):
    bl_idname = "m3.cameras_duplicate"
    bl_label = "Duplicate M3 Camera"
    bl_description = "Duplicates the active M3 camera"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        camera = scene.m3_cameras[scene.m3_camera_index]
        newCamera = scene.m3_cameras.add()

        shared.copyBpyProps(newCamera, camera, skip="name")

        newCamera.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_cameras], prefix=camera.name)

        scene.m3_camera_index = len(scene.m3_cameras) - 1
        return {"FINISHED"}


class M3_PARTICLE_SYSTEMS_OT_create_spawn_points_from_mesh(bpy.types.Operator):
    bl_idname = "m3.create_spawn_points_from_mesh"
    bl_label = "Create Spawn Points From Mesh"
    bl_description = "Uses the vertices of the current mesh as spawn points for particles"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_particle_system_index >= 0:
            particleSystem = scene.m3_particle_systems[scene.m3_particle_system_index]
            particleSystem.spawnPoints.clear()
            activeObject = context.active_object
            if activeObject is not None and activeObject.type == "MESH":
                mesh = activeObject.data
                mesh.update()
                particleSystem.spawnPoints.clear()
                for vertex in mesh.vertices:
                    spawnPoint = particleSystem.spawnPoints.add()
                    spawnPoint.location = vertex.co.copy()
                selectOrCreateBoneForParticleSystem(scene, particleSystem)
                updateBoneShapesOfParticleSystemCopies(scene, particleSystem)
                return {"FINISHED"}
            else:
                raise Exception("No mesh selected")


class M3_PARTICLE_SYSTEMS_OT_add(bpy.types.Operator):
    bl_idname = "m3.particle_systems_add"
    bl_label = "Add Particle System"
    bl_description = "Adds a particle system for the export to the m3 model format"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        particle_system = scene.m3_particle_systems.add()

        propGroups = [scene.m3_particle_systems]
        for particle_system in scene.m3_particle_systems:
            propGroups.append(particle_system.copies)

        particle_system.name = shared.findUnusedPropItemName(scene, propGroups=propGroups)

        if len(scene.m3_material_references) >= 1:
            particle_system.materialName = scene.m3_material_references[0].name

        # The following selection causes a new bone to be created:
        scene.m3_particle_system_index = len(scene.m3_particle_systems) - 1
        return {"FINISHED"}


class M3_PARTICLE_SYSTEMS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.particle_systems_remove"
    bl_label = "Remove Particle System"
    bl_description = "Removes the active M3 particle system"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_particle_system_index >= 0:
            particleSystem = scene.m3_particle_systems[scene.m3_particle_system_index]
            removeBone(scene, particleSystem.boneName)
            for copy in particleSystem.copies:
                removeBone(scene, copy.boneName)
            scene.m3_particle_systems.remove(scene.m3_particle_system_index)

            if scene.m3_particle_system_index != 0 or len(scene.m3_particle_systems) == 0:
                scene.m3_particle_system_index -= 1

        return {"FINISHED"}


class M3_PARTICLE_SYSTEMS_OT_move(bpy.types.Operator):
    bl_idname = "m3.particle_systems_move"
    bl_label = "Move Particle System"
    bl_description = "Moves the active M3 particle system"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_particle_system_index

        if (ii < len(scene.m3_particle_systems) - self.shift and ii >= -self.shift):
            scene.m3_particle_systems.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_particle_systems", ii, self.shift)
            scene.m3_particle_system_index += self.shift

        return {"FINISHED"}


class M3_PARTICLE_SYSTEMS_OT_duplicate(bpy.types.Operator):
    bl_idname = "m3.particle_systems_duplicate"
    bl_label = "Duplicate Particle System"
    bl_description = "Duplicates the active M3 particle system. Particle system copies are not included."
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        particleSystem = scene.m3_particle_systems[scene.m3_particle_system_index]
        newParticleSystem = scene.m3_particle_systems.add()

        propGroups = [scene.m3_particle_systems] + [system.copies for system in scene.m3_particle_systems]

        newParticleSystem.name = shared.findUnusedPropItemName(scene, propGroups=propGroups, prefix=particleSystem.name)
        shared.copyBpyProps(newParticleSystem, particleSystem, skip=["name", "boneName", "copies", "spawnPoints"])

        for spawnPoint in particleSystem.spawnPoints:
            newSpawnPoint = newParticleSystem.spawnPoints.add()

            shared.copyBpyProps(newSpawnPoint, spawnPoint)

        scene.m3_particle_system_index = len(scene.m3_particle_systems) - 1

        return {"FINISHED"}


class M3_PARTICLE_SYSTEM_COPIES_OT_add(bpy.types.Operator):
    bl_idname = "m3.particle_system_copies_add"
    bl_label = "Add Particle System Copy"
    bl_description = "Adds a particle system copy for the export to the m3 model format"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        particleSystemIndex = scene.m3_particle_system_index
        return (particleSystemIndex >= 0 and particleSystemIndex < len(scene.m3_particle_systems))

    def invoke(self, context, event):
        scene = context.scene
        particle_system = scene.m3_particle_systems[scene.m3_particle_system_index]
        copy = particle_system.copies.add()

        propGroups = [scene.m3_particle_systems]
        for particle_system in scene.m3_particle_systems:
            propGroups.append(particle_system.copies)

        copy.name = shared.findUnusedPropItemName(scene, propGroups=propGroups)

        particle_system.copyIndex = len(particle_system.copies) - 1
        return {"FINISHED"}


class M3_PARTICLE_SYSTEMS_COPIES_OT_remove(bpy.types.Operator):
    bl_idname = "m3.particle_system_copies_remove"
    bl_label = "Remove Particle System Copy"
    bl_description = "Removes the active copy from the M3 particle system"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        particleSystemIndex = scene.m3_particle_system_index
        if not (particleSystemIndex >= 0 and particleSystemIndex < len(scene.m3_particle_systems)):
            return False
        particleSystem = scene.m3_particle_systems[particleSystemIndex]
        copyIndex = particleSystem.copyIndex
        return (copyIndex >= 0 and copyIndex < len(particleSystem.copies))

    def invoke(self, context, event):
        scene = context.scene
        particleSystemIndex = scene.m3_particle_system_index
        particleSystem = scene.m3_particle_systems[particleSystemIndex]
        copyIndex = particleSystem.copyIndex
        copy = particleSystem.copies[copyIndex]
        removeBone(scene, copy.boneName)
        particleSystem.copies.remove(particleSystem.copyIndex)

        if particleSystem.copyIndex != 0 or len(particleSystem.copies) == 0:
            particleSystem.copyIndex -= 1

        return {"FINISHED"}


class M3_PARTICLE_SYSTEMS_COPIES_OT_move(bpy.types.Operator):
    bl_idname = "m3.particle_system_copies_move"
    bl_label = "Move Particle System Copy"
    bl_description = "Moves the active M3 particle system copy"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        particleSystem = scene.m3_particle_systems[scene.m3_particle_system_index]
        ii = particleSystem.copyIndex

        if (ii < len(particleSystem.copies) - self.shift and ii >= -self.shift):
            particleSystem.copies.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_particle_systems[{ii}].copies".format(ii=scene.m3_particle_system_index), ii, self.shift)
            particleSystem.copyIndex += self.shift

        return {"FINISHED"}


class M3_RIBBONS_OT_add(bpy.types.Operator):
    bl_idname = "m3.ribbons_add"
    bl_label = "Add Ribbon"
    bl_description = "Adds a ribbon for the export to the m3 model format"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        ribbon = scene.m3_ribbons.add()
        ribbon.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_ribbons])
        if len(scene.m3_material_references) >= 1:
            ribbon.materialName = scene.m3_material_references[0].name

        # The following selection causes a new bone to be created:
        scene.m3_ribbon_index = len(scene.m3_ribbons) - 1
        return {"FINISHED"}


class M3_RIBBONS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.ribbons_remove"
    bl_label = "Remove Ribbon"
    bl_description = "Removes the active M3 ribbon"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_ribbon_index >= 0:
            ribbon = scene.m3_ribbons[scene.m3_ribbon_index]
            removeBone(scene, ribbon.boneName)
            # endPoint do now own the bone, thus we must not delete it:
            # for endPoint in ribbon.endPoints:
            #     removeBone(scene, endPoint.name)
            scene.m3_ribbons.remove(scene.m3_ribbon_index)

            if scene.m3_ribbon_index != 0 or len(scene.m3_ribbons) == 0:
                scene.m3_ribbon_index -= 1

        return {"FINISHED"}


class M3_RIBBONS_OT_move(bpy.types.Operator):
    bl_idname = "m3.ribbons_move"
    bl_label = "Move Ribbon"
    bl_description = "Moves the active M3 ribbon"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_ribbon_index

        if (ii < len(scene.m3_ribbons) - self.shift and ii >= -self.shift):
            scene.m3_ribbons.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_ribbons", ii, self.shift)
            scene.m3_ribbon_index += self.shift

        return {"FINISHED"}


class M3_RIBBONS_OT_duplicate(bpy.types.Operator):
    bl_idname = "m3.ribbons_duplicate"
    bl_label = "Duplicate Ribbon"
    bl_description = "Duplicates the active M3 ribbon. Ribbon end points are not included."
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        ribbon = scene.m3_ribbons[scene.m3_ribbon_index]
        newRibbon = scene.m3_ribbons.add()

        shared.copyBpyProps(newRibbon, ribbon, skip=["name", "boneName", "endPoints"])

        newRibbon.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_ribbons], prefix=ribbon.name)

        scene.m3_ribbon_index = len(scene.m3_ribbons) - 1

        return {"FINISHED"}


class M3_RIBBON_END_POINTS_OT_add(bpy.types.Operator):
    bl_idname = "m3.ribbon_end_points_add"
    bl_label = "Add Ribbon End Point"
    bl_description = "Adds an end point to the current ribbon"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        ribbonIndex = scene.m3_ribbon_index
        ribbon = scene.m3_ribbons[ribbonIndex]
        ribbon.endPoints.add()

        # The following selection causes a new bone to be created:
        ribbon.endPointIndex = len(ribbon.endPoints) - 1
        return {"FINISHED"}


class M3_RIBBON_END_POINTS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.ribbon_end_points_remove"
    bl_label = "Remove RibbonEnd Point"
    bl_description = "Removes the active ribbon end point"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        ribbonIndex = scene.m3_ribbon_index
        ribbon = scene.m3_ribbons[ribbonIndex]

        endPointIndex = ribbon.endPointIndex
        ribbon.endPoints[endPointIndex]
        # end points don"t own bones yet:
        # removeBone(scene, endPoint.name)
        ribbon.endPoints.remove(endPointIndex)

        if ribbon.endPointIndex != 0 or len(ribbon.endPoints) == 0:
            ribbon.endPointIndex -= 1

        return {"FINISHED"}


class M3_RIBBON_END_POINTS_OT_move(bpy.types.Operator):
    bl_idname = "m3.ribbon_end_points_move"
    bl_label = "Move Ribbon End Point"
    bl_description = "Moves the active M3 ribbon end point"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ribbon = scene.m3_ribbons[scene.m3_ribbon_index]
        ii = ribbon.endPointIndex

        if (ii < len(ribbon.endPoints) - self.shift and ii >= -self.shift):
            ribbon.endPoints.move(ii, ii + self.shift)
            ribbon.endPointIndex += self.shift

        return {"FINISHED"}


class M3_FORCES_OT_add(bpy.types.Operator):
    bl_idname = "m3.forces_add"
    bl_label = "Add Force"
    bl_description = "Adds a particle system force for the export to the m3 model format"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        force = scene.m3_forces.add()
        force.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_forces])

        # The following selection causes a new bone to be created:
        scene.m3_force_index = len(scene.m3_forces) - 1
        return {"FINISHED"}


class M3_FORCES_OT_remove(bpy.types.Operator):
    bl_idname = "m3.forces_remove"
    bl_label = "Remove M3 Force"
    bl_description = "Removes the active M3 particle system force"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_force_index >= 0:
            force = scene.m3_forces[scene.m3_force_index]
            removeBone(scene, force.boneName)
            scene.m3_forces.remove(scene.m3_force_index)

            if scene.m3_force_index != 0 or len(scene.m3_forces) == 0:
                scene.m3_force_index -= 1

        return {"FINISHED"}


class M3_FORCES_OT_move(bpy.types.Operator):
    bl_idname = "m3.forces_move"
    bl_label = "Move Force"
    bl_description = "Moves the active M3 force"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_force_index

        if (ii < len(scene.m3_forces) - self.shift and ii >= -self.shift):
            scene.m3_forces.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_forces", ii, self.shift)
            scene.m3_force_index += self.shift

        return {"FINISHED"}


class M3_FORCES_OT_duplicate(bpy.types.Operator):
    bl_idname = "m3.forces_duplicate"
    bl_label = "Duplicate M3 Force"
    bl_description = "Duplicates the active M3 force"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        force = scene.m3_forces[scene.m3_force_index]
        newForce = scene.m3_forces.add()

        shared.copyBpyProps(newForce, force, skip=["name", "boneName"])
        newForce.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_forces], prefix=force.name)

        scene.m3_force_index = len(scene.m3_forces) - 1

        return {"FINISHED"}


class M3_RIGID_BODIES_OT_add(bpy.types.Operator):
    bl_idname = "m3.rigid_bodies_add"
    bl_label = "Add Rigid Body"
    bl_description = "Adds a rigid body for export to the m3 model format"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        rigid_body = scene.m3_rigid_bodies.add()

        rigid_body.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_rigid_bodies])
        rigid_body.boneName = ""

        scene.m3_rigid_body_index = len(scene.m3_rigid_bodies) - 1
        return {"FINISHED"}


class M3_RIGID_BODIES_OT_remove(bpy.types.Operator):
    bl_idname = "m3.rigid_bodies_remove"
    bl_label = "Remove M3 Rigid Body"
    bl_description = "Removes the active M3 rigid body (and the M3 Physics Shapes it contains)"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene

        currentIndex = scene.m3_rigid_body_index
        if not 0 <= currentIndex < len(scene.m3_rigid_bodies):
            return {"CANCELLED"}

        shared.removeRigidBodyBoneShape(scene, scene.m3_rigid_bodies[currentIndex].name)

        scene.m3_rigid_bodies.remove(currentIndex)

        if scene.m3_rigid_body_index != 0 or len(scene.m3_rigid_bodies) == 0:
            scene.m3_rigid_body_index -= 1

        return {"FINISHED"}


class M3_RIGID_BODIES_OT_move(bpy.types.Operator):
    bl_idname = "m3.rigid_bodies_move"
    bl_label = "Move Force"
    bl_description = "Moves the active M3 rigid body"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_rigid_body_index

        if (ii < len(scene.m3_rigid_bodies) - self.shift and ii >= -self.shift):
            scene.m3_rigid_bodies.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_rigid_bodies", ii, self.shift)
            scene.m3_rigid_body_index += self.shift

        return {"FINISHED"}


class M3_RIGID_BODIES_OT_duplicate(bpy.types.Operator):
    bl_idname = "m3.rigid_bodies_duplicate"
    bl_label = "Duplicate M3 Rigid Body"
    bl_description = "Duplicates the active M3 rigid body"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        rigidBody = scene.m3_rigid_bodies[scene.m3_rigid_body_index]
        newRigidBody = scene.m3_rigid_bodies.add()

        shared.copyBpyProps(newRigidBody, rigidBody, skip=["physicsShapes", "boneName"])

        for physicsShape in rigidBody.physicsShapes:
            newPhysicsShape = newRigidBody.physicsShapes.add()

            shared.copyBpyProps(newPhysicsShape, physicsShape)

        newRigidBody.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_rigid_bodies])

        scene.m3_rigid_body_index = len(scene.m3_rigid_bodies) - 1
        return {"FINISHED"}


class M3_PHYSICS_SHAPES_OT_add(bpy.types.Operator):
    bl_idname = "m3.physics_shapes_add"
    bl_label = "Add Physics Shape"
    bl_description = "Adds an M3 physics shape to the active M3 rigid body"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene

        currentIndex = scene.m3_rigid_body_index
        rigid_body = scene.m3_rigid_bodies[currentIndex]

        physics_shape = rigid_body.physicsShapes.add()
        physics_shape.nameOld = physics_shape.name = shared.findUnusedPropItemName(scene, propGroups=[rigid_body.physicsShapes])

        rigid_body.physicsShapeIndex = len(rigid_body.physicsShapes) - 1
        shared.updateBoneShapeOfRigidBody(scene, rigid_body, rigid_body.name)

        return {"FINISHED"}


class M3_PHYSICS_SHAPES_OT_remove(bpy.types.Operator):
    bl_idname = "m3.physics_shapes_remove"
    bl_label = "Remove M3 Physics Shape"
    bl_description = "Removes the active M3 physics shape"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene

        currentIndex = scene.m3_rigid_body_index
        rigid_body = scene.m3_rigid_bodies[currentIndex]

        currentIndex = rigid_body.physicsShapeIndex
        rigid_body.physicsShapes.remove(currentIndex)

        if rigid_body.physicsShapeIndex != 0 or len(rigid_body.physicsShapes) == 0:
            rigid_body.physicsShapeIndex -= 1
        shared.updateBoneShapeOfRigidBody(scene, rigid_body, rigid_body.name)

        return {"FINISHED"}


class M3_PHYSICS_SHAPES_OT_move(bpy.types.Operator):
    bl_idname = "m3.physics_shapes_move"
    bl_label = "Move Force"
    bl_description = "Moves the active M3 rigid body"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        rigidBody = scene.m3_rigid_bodies[scene.m3_rigid_body_index]
        ii = rigidBody.physicsShapeIndex

        if (ii < len(rigidBody.physicsShapes) - self.shift and ii >= -self.shift):
            rigidBody.physicsShapes.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_rigid_bodies[{ii}].physicsShapes".format(ii=scene.m3_rigid_body_index), ii, self.shift)
            rigidBody.physicsShapeIndex += self.shift

        return {"FINISHED"}


class M3_LIGHTS_OT_add(bpy.types.Operator):
    bl_idname = "m3.lights_add"
    bl_label = "Add Light"
    bl_description = "Adds a light for the export to the m3 model format"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        light = scene.m3_lights.add()
        light.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_lights])

        # The following selection causes a new bone to be created:
        scene.m3_light_index = len(scene.m3_lights) - 1

        return {"FINISHED"}


class M3_LIGHTS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.lights_remove"
    bl_label = "Remove M3 Light"
    bl_description = "Removes the active M3 light"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        light = scene.m3_lights[scene.m3_light_index]
        removeBone(scene, light.boneName)
        scene.m3_lights.remove(scene.m3_light_index)

        if scene.m3_light_index != 0 or len(scene.m3_lights) == 0:
            scene.m3_light_index -= 1

        return {"FINISHED"}


class M3_LIGHTS_OT_move(bpy.types.Operator):
    bl_idname = "m3.lights_move"
    bl_label = "Move Light"
    bl_description = "Moves the active M3 light"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_light_index

        if (ii < len(scene.m3_lights) - self.shift and ii >= -self.shift):
            scene.m3_lights.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_lights", ii, self.shift)
            scene.m3_light_index += self.shift

        return {"FINISHED"}


class M3_LIGHTS_OT_duplicate(bpy.types.Operator):
    bl_idname = "m3.lights_duplicate"
    bl_label = "Duplicate Light"
    bl_description = "Duplicates the active M3 light"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        light = scene.m3_lights[scene.m3_light_index]
        newLight = scene.m3_lights.add()

        shared.copyBpyProps(newLight, light, skip=["name", "boneName"])
        newLight.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_lights], prefix=light.name)

        scene.m3_light_index = len(scene.m3_lights) - 1
        return {"FINISHED"}


class M3_BILLBOARD_BEHAVIORS_OT_add(bpy.types.Operator):
    bl_idname = "m3.billboard_behaviors_add"
    bl_label = "Add Billboard Behavior"
    bl_description = "Adds a billboard behavior"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        behavior = scene.m3_billboard_behaviors.add()

        behavior.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_billboard_behaviors])

        # The following selection causes a new bone to be created:
        scene.m3_billboard_behavior_index = len(scene.m3_billboard_behaviors) - 1

        return {"FINISHED"}


class M3_BILLBOARD_BEHAVIORS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.billboard_behaviors_remove"
    bl_label = "Remove M3 Billboard Behavior"
    bl_description = "Removes the active M3 billboard behavior"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_billboard_behavior_index >= 0:
            scene.m3_billboard_behaviors.remove(scene.m3_billboard_behavior_index)

            if scene.m3_billboard_behavior_index != 0 or len(scene.m3_billboard_behaviors) == 0:
                scene.m3_billboard_behavior_index -= 1

        return {"FINISHED"}


class M3_BILLBOARD_BEHAVIORS_OT_move(bpy.types.Operator):
    bl_idname = "m3.billboard_behaviors_move"
    bl_label = "Move Billboard Behavior"
    bl_description = "Moves the active M3 billboard behavior"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_billboard_behavior_index

        if (ii < len(scene.m3_billboard_behaviors) - self.shift and ii >= -self.shift):
            scene.m3_billboard_behaviors.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_billboard_behaviors", ii, self.shift)
            scene.m3_billboard_behavior_index += self.shift

        return {"FINISHED"}


class M3_INVERSE_KINEMATIC_CHAINS_OT_add(bpy.types.Operator):
    bl_idname = "m3.ik_chains_add"
    bl_label = "Add M3 Inverse Kinematic Chain"
    bl_description = "Adds an M3 inverse kinematic chain"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        ik = scene.m3_ik_chains.add()

        ik.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_ik_chains])

        # The following selection causes a new bone to be created:
        scene.m3_ik_chain_index = len(scene.m3_ik_chains) - 1

        return {"FINISHED"}


class M3_INVERSE_KINEMATIC_CHAINS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.ik_chains_remove"
    bl_label = "Remove M3 Inverse Kinematic Chain"
    bl_description = "Removes the active M3 inverse kinematic chain"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_ik_chain_index >= 0:
            scene.m3_ik_chains.remove(scene.m3_ik_chain_index)

            if scene.m3_ik_chain_index != 0 or len(scene.m3_ik_chains) == 0:
                scene.m3_ik_chain_index -= 1

        return {"FINISHED"}


class M3_INVERSE_KINEMATIC_CHAINS_OT_move(bpy.types.Operator):
    bl_idname = "m3.ik_chains_move"
    bl_label = "Move M3 Inverse Kinematic Chain"
    bl_description = "Moves the active M3 inverse kinematic chain"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_ik_chain_index

        if (ii < len(scene.m3_ik_chains) - self.shift and ii >= -self.shift):
            scene.m3_ik_chains.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_ik_chains", ii, self.shift)
            scene.m3_ik_chain_index += self.shift

        return {"FINISHED"}


class M3_TURRET_BEHAVIORS_OT_add(bpy.types.Operator):
    bl_idname = "m3.turret_behaviors_add"
    bl_label = "Add M3 Turret Behavior"
    bl_description = "Adds an M3 turret behavior"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        turret = scene.m3_turret_behaviors.add()

        turret.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_turret_behaviors])

        # The following selection causes a new bone to be created:
        scene.m3_turret_behavior_index = len(scene.m3_turret_behaviors) - 1

        return {"FINISHED"}


class M3_TURRET_BEHAVIORS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.turret_behaviors_remove"
    bl_label = "Remove M3 Turret Behavior"
    bl_description = "Removes the active M3 turret behavior"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_turret_behavior_index >= 0:
            scene.m3_turret_behaviors.remove(scene.m3_turret_behavior_index)

            if scene.m3_turret_behavior_index != 0 or len(scene.m3_turret_behaviors) == 0:
                scene.m3_turret_behavior_index -= 1

        return {"FINISHED"}


class M3_TURRET_BEHAVIORS_OT_move(bpy.types.Operator):
    bl_idname = "m3.turret_behaviors_move"
    bl_label = "Move M3 Turret Behavior"
    bl_description = "Moves the active M3 turret behavior"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_turret_behavior_index

        if (ii < len(scene.m3_turret_behaviors) - self.shift and ii >= -self.shift):
            scene.m3_turret_behaviors.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_turret_behaviors", ii, self.shift)
            scene.m3_turret_behavior_index += self.shift

        return {"FINISHED"}


class M3_TURRET_BEHAVIOR_PARTS_OT_add(bpy.types.Operator):
    bl_idname = "m3.turret_behavior_parts_add"
    bl_label = "Add M3 Turret Behavior Part"
    bl_description = "Adds an M3 turret behavior part"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        turret = scene.m3_turret_behaviors[scene.m3_turret_behavior_index]
        part = turret.parts.add()

        part.name = shared.findUnusedPropItemName(scene, propGroups=[turret.parts])

        # The following selection causes a new bone to be created:
        turret.parts_index = len(turret.parts) - 1

        return {"FINISHED"}


class M3_TURRET_BEHAVIOR_PARTS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.turret_behavior_parts_remove"
    bl_label = "Remove M3 Turret Behavior"
    bl_description = "Removes the active M3 turret behavior"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        turret = scene.m3_turret_behaviors[scene.m3_turret_behavior_index]
        if turret.part_index >= 0:
            turret.parts.remove(turret.part_index)

            if turret.part_index != 0 or len(turret.parts) == 0:
                turret.part_index -= 1

        return {"FINISHED"}


class M3_TURRET_BEHAVIOR_PARTS_OT_move(bpy.types.Operator):
    bl_idname = "m3.turret_behavior_parts_move"
    bl_label = "Move M3 Turret Behavior"
    bl_description = "Moves the active M3 turret behavior"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        turret = scene.m3_turret_behaviors[scene.m3_turret_behavior_index]
        ii = turret.part_index

        if (ii < len(turret.parts) - self.shift and ii >= -self.shift):
            turret.parts.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_turret_behaviors", ii, self.shift)
            turret.part_index += self.shift

        return {"FINISHED"}


class M3_PHYSICS_JOINTS_OT_add(bpy.types.Operator):
    bl_idname = "m3.physics_joints_add"
    bl_label = "Add M3 Physics Joint"
    bl_description = "Adds an M3 physics joint"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        joint = scene.m3_physics_joints.add()

        joint.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_physics_joints])

        # The following selection causes a new bone to be created:
        scene.m3_physics_joint_index = len(scene.m3_physics_joints) - 1

        return {"FINISHED"}


class M3_PHYSICS_JOINTS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.physics_joints_remove"
    bl_label = "Remove M3 Physics Joint"
    bl_description = "Removes the active M3 physics joint"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_physics_joint_index >= 0:
            scene.m3_physics_joints.remove(scene.m3_physics_joint_index)

            if scene.m3_physics_joint_index != 0 or len(scene.m3_physics_joints) == 0:
                scene.m3_physics_joint_index -= 1

        return {"FINISHED"}


class M3_PHYSICS_JOINTS_OT_move(bpy.types.Operator):
    bl_idname = "m3.physics_joints_move"
    bl_label = "Move M3 Physics Joint"
    bl_description = "Moves the active M3 physics joint"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_physics_joint_index

        if (ii < len(scene.m3_physics_joints) - self.shift and ii >= -self.shift):
            scene.m3_physics_joints.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_physics_joints", ii, self.shift)
            scene.m3_physics_joint_index += self.shift

        return {"FINISHED"}


class M3_WARPS_OT_add(bpy.types.Operator):
    bl_idname = "m3.warps_add"
    bl_label = "Add Warp Field"
    bl_description = "Adds a warp field for the export to the m3 model format"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        warp = scene.m3_warps.add()
        warp.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_warps])

        # The following selection causes a new bone to be created:
        scene.m3_warp_index = len(scene.m3_warps) - 1

        return {"FINISHED"}


class M3_WARPS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.warps_remove"
    bl_label = "Remove M3 Warp Field"
    bl_description = "Removes the active M3 warp field"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_warp_index >= 0:
            warp = scene.m3_warps[scene.m3_warp_index]
            removeBone(scene, warp.boneName)
            scene.m3_warps.remove(scene.m3_warp_index)

            if scene.m3_warp_index != 0 or len(scene.m3_warps) == 0:
                scene.m3_warp_index -= 1

        return {"FINISHED"}


class M3_WARPS_OT_move(bpy.types.Operator):
    bl_idname = "m3.warps_move"
    bl_label = "Move M3 Warp Field"
    bl_description = "Moves the active M3 warp field"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_warp_index

        if (ii < len(scene.m3_warps) - self.shift and ii >= -self.shift):
            scene.m3_warps.move(ii, ii + self.shift)
            swapActionSceneM3Keyframes("m3_warps", ii, self.shift)
            scene.m3_warp_index += self.shift

        return {"FINISHED"}


class M3_WARPS_OT_duplicate(bpy.types.Operator):
    bl_idname = "m3.warps_duplicate"
    bl_label = "Duplicate M3 Warp Field"
    bl_description = "Duplicates the active M3 warp field"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        warp = scene.m3_warps[scene.m3_warp_index]
        newWarp = scene.m3_warps.add()

        shared.copyBpyProps(newWarp, warp, skip=["name", "boneName"])
        newWarp.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_warps], prefix=warp.name)

        scene.m3_warp_index = len(scene.m3_warps) - 1
        return {"FINISHED"}


class M3_TIGHT_HIT_TESTS_OT_selectorcreatebone(bpy.types.Operator):
    bl_idname = "m3.tight_hit_test_select_or_create_bone"
    bl_label = "Select or create the HitTestFuzzy bone"
    bl_description = "Adds a shape for the fuzzy hit test"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        tightHitTest = scene.m3_tight_hit_test
        tightHitTest.boneName = shared.tightHitTestBoneName
        selectOrCreateBoneForShapeObject(scene, tightHitTest)
        return {"FINISHED"}


class M3_TIGHT_HIT_TESTS_OT_hittestremove(bpy.types.Operator):
    bl_idname = "m3.tight_hit_test_remove"
    bl_label = "Select or create the HitTestFuzzy bone"
    bl_description = "Adds a shape for the fuzzy hit test"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        tightHitTest = scene.m3_tight_hit_test
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode="EDIT")
        removeBone(scene, tightHitTest.boneName)
        tightHitTest.name = ""

        return {"FINISHED"}


class M3_FUZZY_HIT_TESTS_OT_add(bpy.types.Operator):
    bl_idname = "m3.fuzzy_hit_tests_add"
    bl_label = "Add Fuzzy Hit Test Shape"
    bl_description = "Adds a shape for the fuzzy hit test"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        m3_fuzzy_hit_test = scene.m3_fuzzy_hit_tests.add()
        m3_fuzzy_hit_test.boneName = self.findUnusedBoneName(scene)

        # The following selection causes a new bone to be created:
        scene.m3_fuzzy_hit_test_index = len(scene.m3_fuzzy_hit_tests) - 1
        return {"FINISHED"}

    def findUnusedBoneName(self, scene):
        usedNames = set()
        for m3_fuzzy_hit_test in scene.m3_fuzzy_hit_tests:
            usedNames.add(m3_fuzzy_hit_test.boneName)
        unusedName = None
        bestName = "HitTestFuzzy"
        if bestName not in usedNames:
            unusedName = bestName
        counter = 1
        while unusedName is None:
            suggestedName = bestName + ("%02d" % counter)
            if suggestedName not in usedNames:
                unusedName = suggestedName
            counter += 1
        return unusedName


class M3_FUZZY_HIT_TESTS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.fuzzy_hit_tests_remove"
    bl_label = "Remove Fuzzy Hit Test Shape"
    bl_description = "Removes a fuzzy hit test shape"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_fuzzy_hit_test_index >= 0:
            hitTest = scene.m3_fuzzy_hit_tests[scene.m3_fuzzy_hit_test_index]
            removeBone(scene, hitTest.boneName)
            scene.m3_fuzzy_hit_tests.remove(scene.m3_fuzzy_hit_test_index)

            if scene.m3_fuzzy_hit_test_index != 0 or len(scene.m3_fuzzy_hit_tests) == 0:
                scene.m3_fuzzy_hit_test_index -= 1

        return {"FINISHED"}


class M3_FUZZY_HIT_TESTS_OT_move(bpy.types.Operator):
    bl_idname = "m3.fuzzy_hit_tests_move"
    bl_label = "Move Fuzzy Hit Test Shape"
    bl_description = "Moves a fuzzy hit test shape"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_fuzzy_hit_test_index

        if (ii < len(scene.m3_fuzzy_hit_tests) - self.shift and ii >= -self.shift):
            scene.m3_fuzzy_hit_tests.move(ii, ii + self.shift)
            scene.m3_fuzzy_hit_test_index += self.shift

        return {"FINISHED"}


class M3_ATTACHMENT_POINTS_OT_add(bpy.types.Operator):
    bl_idname = "m3.attachment_points_add"
    bl_label = "Add Attachment Point"
    bl_description = "Adds an attachment point for the export to Starcraft 2"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        attachmentPoint = scene.m3_attachment_points.add()
        attachmentPoint.name = shared.findUnusedPropItemName(scene, propGroups=[scene.m3_attachment_points], suggestedNames=["Origin", "Center", "Overhead", "Target"], prefix="Target")

        # The following selection causes a new bone to be created:
        scene.m3_attachment_point_index = len(scene.m3_attachment_points) - 1
        return {"FINISHED"}


class M3_ATTACHMENT_POINTS_OT_remove(bpy.types.Operator):
    bl_idname = "m3.attachment_points_remove"
    bl_label = "Remove Attachment Point"
    bl_description = "Removes the active M3 attachment point"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.m3_attachment_point_index >= 0:
            attackmentPoint = scene.m3_attachment_points[scene.m3_attachment_point_index]
            removeBone(scene, attackmentPoint.boneName)
            scene.m3_attachment_points.remove(scene.m3_attachment_point_index)

            if scene.m3_attachment_point_index != 0 or len(scene.m3_attachment_points) == 0:
                scene.m3_attachment_point_index -= 1

        return {"FINISHED"}


class M3_ATTACHMENT_POINTS_OT_move(bpy.types.Operator):
    bl_idname = "m3.attachment_points_move"
    bl_label = "Move Attachment Point"
    bl_description = "Moves the active attachment point"
    bl_options = {"UNDO"}

    shift: bpy.props.IntProperty(name="shift", default=0)

    def invoke(self, context, event):
        scene = context.scene
        ii = scene.m3_attachment_point_index

        if (ii < len(scene.m3_attachment_points) - self.shift and ii >= -self.shift):
            scene.m3_attachment_points.move(ii, ii + self.shift)
            scene.m3_attachment_point_index += self.shift

        return {"FINISHED"}


class M3_OT_generateBlenderMaterails(bpy.types.Operator):
    bl_idname = "m3.generate_blender_materials"
    bl_label = "M3 -> blender materials"
    bl_description = "Generates blender materials based on the specified m3 materials and imports textures as necessary from the specified path"

    def invoke(self, context, event):
        scene = context.scene

        shared.createBlenderMaterialsFromM3Materials(scene)
        return {"FINISHED"}


class M3_OT_conertBlenderToM3NormalMap(bpy.types.Operator):
    """Convert a blender normal map to a M3 one"""
    bl_idname = "m3.convert_blender_to_m3_normal_map"
    bl_label = "Converts a classic normal map to a normal map usable in the m3 format"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        if not hasattr(context, "edit_image"):
            return False
        return context.edit_image is not None

    def invoke(self, context, event):
        currentImage = context.edit_image
        values = list(currentImage.pixels)

        def getNewValue(absoluteIndex):
            colorIndex = absoluteIndex % 4
            # Blender: R = (left/right), G = (up/down) , B = (height), A = (unused)
            # M3:      R = (unused)    , G = (down/up?),  B = (unused), A = (left/right)

            if colorIndex == 0:  # red color slot:
                # unused
                return 1.0
            elif colorIndex == 1:  # green color slot
                # m3.G = blender.G
                return 1.0 - values[absoluteIndex]
            elif colorIndex == 2:  # blue color slot
                # unused ?
                return 0.0
            if colorIndex == 3:  # change alpha
                # m3.A = blender.R
                # to get from index pixelOffset+0 to pixelOffset+3: add 3
                return values[absoluteIndex - 3]

        currentImage.pixels = [getNewValue(i) for i in range(len(values))]
        currentImage.update()
        return {"FINISHED"}


class M3_OT_conertM3ToBlenderNormalMap(bpy.types.Operator):
    """Convert a m3 normal map to a blender one"""
    bl_idname = "m3.convert_m3_to_blender_normal_map"
    bl_label = "Converts a m3 normal map to a classic normal map"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        if not hasattr(context, "edit_image"):
            return False
        return context.edit_image is not None

    def invoke(self, context, event):
        currentImage = context.edit_image
        values = list(currentImage.pixels)

        def getNewValue(absoluteIndex):
            colorIndex = absoluteIndex % 4
            # Blender: R = (left/right), G = (up/down) , B = (height), A = (unused)
            # M3:      R = (unused)    , G = (down/up?),  B = (unused), A = (left/right)

            if colorIndex == 0:  # red color slot:
                # blender.R = m3.A
                return values[absoluteIndex + 3]  # old alpha
            elif colorIndex == 1:  # green color slot
                # blender.G = 1.0 - m3.G
                return 1.0 - values[absoluteIndex]
            elif colorIndex == 2:  # blue color slot
                newRed = values[absoluteIndex + 1]  # (newRed = old alpha)
                newGreen = 1.0 - values[absoluteIndex - 1]  # 1.0 - old green
                leftRight = 2 * (newRed - 0.5)
                upDown = 2 * (newGreen - 0.5)
                # since sqrt(lowHigh^2 + leftRight^2 + upDown^2) = 1.0 is
                # newBlue = math.sqrt(1.0 - newRed*newRed - newGreen*newGreen)
                return math.sqrt(max(0, 1 - leftRight * leftRight - upDown * upDown))
            if colorIndex == 3:  # change alpha
                # unused
                return 1.0

        currentImage.pixels = [getNewValue(i) for i in range(len(values))]
        currentImage.update()
        return {"FINISHED"}


def getSignGroup(bm):
    return bm.faces.layers.int.get("m3sign") or bm.faces.layers.int.new("m3sign")


class ObjectSignPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_M3_sign"
    bl_label = "M3 Vertex Signs"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"
    bl_mode = "edit"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == "MESH"

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.operator("m3.vertex_sign_select", text="Select")
        col = layout.column_flow(columns=2)
        col.operator("m3.vertex_sign_set", text="Set To Selected")
        col.operator("m3.vertex_sign_invert", text="Invert Selected")
        col.operator("m3.vertex_sign_add", text="Add Selected")
        col.operator("m3.vertex_sign_remove", text="Remove Selected")


class ObjectSignOpSet(bpy.types.Operator):
    bl_idname = "m3.vertex_sign_set"
    bl_label = "Set faces"
    bl_description = "Sets the vertices of all selected faces normal sign to positive, and all unselected to negative"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        mesh = context.object.data
        bm = bmesh.from_edit_mesh(mesh)

        layer = getSignGroup(bm)
        for face in bm.faces:
            face[layer] = 1 if face.select else 0

        bmesh.update_edit_mesh(mesh)

        return {"FINISHED"}


class ObjectSignOpSelect(bpy.types.Operator):
    bl_idname = "m3.vertex_sign_select"
    bl_label = "Select faces"
    bl_description = "Selects all vertices with a positive normal sign"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        mesh = context.object.data
        bm = bmesh.from_edit_mesh(mesh)

        layer = getSignGroup(bm)
        for face in bm.faces:
            if face[layer] == 1:
                face.select = True

        bmesh.update_edit_mesh(mesh)

        return {"FINISHED"}


class ObjectSignOpAdd(bpy.types.Operator):
    bl_idname = "m3.vertex_sign_add"
    bl_label = "Add faces"
    bl_description = "Sets the normal sign of the vertices of all selected faces to positive"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        mesh = context.object.data
        bm = bmesh.from_edit_mesh(mesh)

        layer = getSignGroup(bm)
        for face in bm.faces:
            if face.select:
                face[layer] = 1

        bmesh.update_edit_mesh(mesh)

        return {"FINISHED"}


class ObjectSignOpRemove(bpy.types.Operator):
    bl_idname = "m3.vertex_sign_remove"
    bl_label = "Remove faces"
    bl_description = "Sets the normal sign of the vertices of all selected faces to negative"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        mesh = context.object.data
        bm = bmesh.from_edit_mesh(mesh)

        layer = getSignGroup(bm)
        for face in bm.faces:
            if face.select:
                face[layer] = -1

        bmesh.update_edit_mesh(mesh)

        return {"FINISHED"}


class ObjectSignOpInvert(bpy.types.Operator):
    bl_idname = "m3.vertex_sign_invert"
    bl_label = "Invert faces"
    bl_description = "Inverts the value of the sign inversion group for the selected faces."
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        mesh = context.object.data
        bm = bmesh.from_edit_mesh(mesh)

        layer = getSignGroup(bm)
        for face in bm.faces:
            if face.select is True:
                face[layer] = 1 if face[layer] == 0 else 0

        bmesh.update_edit_mesh(mesh)

        return {"FINISHED"}


def menu_func_convertNormalMaps(self, context):
    self.layout.operator(M3_OT_conertBlenderToM3NormalMap.bl_idname, text="Convert Blender to M3 Normal Map")
    self.layout.operator(M3_OT_conertM3ToBlenderNormalMap.bl_idname, text="Convert M3 to Blender Normal Map")


def menu_func_import(self, context):
    self.layout.operator(ui.M3_OT_import.bl_idname, text="StarCraft 2 Model / Animation (.m3/.m3a)...")


def menu_func_export(self, context):
    self.layout.operator(ui.M3_OT_export.bl_idname, text="StarCraft 2 Model (.m3)...")


classes = (
    M3AnimatedPropertyReference,
    M3TransformationCollection,
    cm.M3MaterialLayer,
    M3CompositeMaterialSection,
    M3ParticleSpawnPoint,
    M3ParticleSystemCopy,
    M3RibbonEndPoint,
    M3PhysicsShape,
    M3Animation,
    cm.M3Material,
    M3StandardMaterial,
    M3DisplacementMaterial,
    M3CompositeMaterial,
    M3TerrainMaterial,
    M3VolumeMaterial,
    M3VolumeNoiseMaterial,
    M3CreepMaterial,
    M3STBMaterial,
    M3LensFlareMaterial,
    M3MaterialNode,
    M3Camera,
    M3ParticleSystem,
    M3Ribbon,
    M3Force,
    M3RigidBody,
    M3Light,
    M3BillboardBehavior,
    M3InverseKinematicChain,
    M3TurretBehaviorPart,
    M3TurretBehavior,
    M3PhysicsJoint,
    cm.M3GroupProjection,
    M3Warp,
    M3AttachmentPoint,
    cm.M3ExportOptions,
    cm.M3ImportContent,
    cm.M3ImportOptions,
    M3BoneVisiblityOptions,
    M3Boundings,
    M3AnimIdData,
    M3SimpleGeometricShape,
    BoneVisibilityPanel,
    AnimationSequencesMenu,
    AnimationSequencesPanel,
    AnimationSequencesPropPanel,
    AnimationSequenceTransformationCollectionsPanel,
    MaterialReferencesMenu,
    MaterialReferencesPanel,
    MaterialSelectionPanel,
    MaterialPropertiesPanel,
    MaterialPropertiesFlagsPanel,
    ObjectMaterialPropertiesPanel,
    ObjectMaterialPropertiesFlagsPanel,
    MaterialLayersPanel,
    ObjectMaterialLayersPanel,
    MaterialLayersColorPanel,
    ObjectMaterialLayersColorPanel,
    MaterialLayersUvPanel,
    ObjectMaterialLayersUvPanel,
    MaterialLayersFresnelPanel,
    ObjectMaterialLayersFresnelPanel,
    MaterialLayersRTTPanel,
    ObjectMaterialLayersRTTPanel,
    CameraMenu,
    CameraPanel,
    ParticleSystemsMenu,
    ParticleSystemsPanel,
    ParticleSystemCopiesPanel,
    ParticleSystemsPropPanel,
    ParticleSystemsAreaPanel,
    ParticleSystemsMovementPanel,
    ParticleSystemsColorPanel,
    ParticleSystemsSizePanel,
    ParticleSystemsRotationPanel,
    ParticleSystemsImageAnimPanel,
    ParticleSystemsFlagsPanel,
    RibbonsMenu,
    RibbonsPanel,
    RibbonEndPointsPanel,
    RibbonPropertiesPanel,
    RibbonColorPanel,
    RibbonScalePanel,
    RibbonFlagsPanel,
    ForceMenu,
    ForcePanel,
    RigidBodyMenu,
    RigidBodyPanel,
    PhysicsShapePanel,
    RigidBodyPropertiesPanel,
    RigidBodyForcesPanel,
    RigidBodyFlagsPanel,
    PhysicsMeshPanel,
    VisbilityTestPanel,
    LightMenu,
    LightPanel,
    BillboardBehaviorPanel,
    InverseKinematicChainPanel,
    TurretBehaviorPanel,
    PhysicsJointPanel,
    ui.ProjectionMenu,
    ui.ProjectionPanel,
    WarpMenu,
    WarpPanel,
    AttachmentPointsPanel,
    FuzzyHitTestPanel,
    TightHitTestPanel,
    ExtraBonePropertiesPanel,
    ObjectSignPanel,
    ObjectSignOpSet,
    ObjectSignOpSelect,
    ObjectSignOpAdd,
    ObjectSignOpRemove,
    ObjectSignOpInvert,
    M3_MATERIALS_OT_add,
    M3_MATERIALS_OT_createForMesh,
    M3_MATERIALS_OT_remove,
    M3_MATERIALS_OT_move,
    M3_MATERIALS_OT_duplicate,
    M3_COMPOSITE_MATERIAL_OT_add_section,
    M3_COMPOSITE_MATERIAL_OT_remove_section,
    M3_COMPOSITE_MATERIAL_OT_move_section,
    M3_ANIMATIONS_OT_add,
    M3_ANIMATIONS_OT_remove,
    M3_ANIMATIONS_OT_move,
    M3_ANIMATIONS_OT_duplicate,
    M3_ANIMATIONS_OT_deselect,
    M3_ANIMATIONS_OT_STC_add,
    M3_ANIMATIONS_OT_STC_remove,
    M3_ANIMATIONS_OT_STC_move,
    M3_ANIMATIONS_OT_STC_select,
    M3_ANIMATIONS_OT_STC_assign,
    M3_CAMERAS_OT_add,
    M3_CAMERAS_OT_remove,
    M3_CAMERAS_OT_move,
    M3_CAMERAS_OT_duplicate,
    M3_PARTICLE_SYSTEMS_OT_create_spawn_points_from_mesh,
    M3_PARTICLE_SYSTEMS_OT_add,
    M3_PARTICLE_SYSTEMS_OT_remove,
    M3_PARTICLE_SYSTEMS_OT_move,
    M3_PARTICLE_SYSTEMS_OT_duplicate,
    M3_PARTICLE_SYSTEM_COPIES_OT_add,
    M3_PARTICLE_SYSTEMS_COPIES_OT_remove,
    M3_PARTICLE_SYSTEMS_COPIES_OT_move,
    M3_RIBBONS_OT_add,
    M3_RIBBONS_OT_remove,
    M3_RIBBONS_OT_move,
    M3_RIBBONS_OT_duplicate,
    M3_RIBBON_END_POINTS_OT_add,
    M3_RIBBON_END_POINTS_OT_remove,
    M3_RIBBON_END_POINTS_OT_move,
    M3_FORCES_OT_add,
    M3_FORCES_OT_remove,
    M3_FORCES_OT_move,
    M3_FORCES_OT_duplicate,
    M3_RIGID_BODIES_OT_add,
    M3_RIGID_BODIES_OT_remove,
    M3_RIGID_BODIES_OT_move,
    M3_RIGID_BODIES_OT_duplicate,
    M3_PHYSICS_SHAPES_OT_add,
    M3_PHYSICS_SHAPES_OT_remove,
    M3_PHYSICS_SHAPES_OT_move,
    M3_PHYSICS_JOINTS_OT_add,
    M3_PHYSICS_JOINTS_OT_remove,
    M3_PHYSICS_JOINTS_OT_move,
    M3_LIGHTS_OT_add,
    M3_LIGHTS_OT_remove,
    M3_LIGHTS_OT_move,
    M3_LIGHTS_OT_duplicate,
    M3_BILLBOARD_BEHAVIORS_OT_add,
    M3_BILLBOARD_BEHAVIORS_OT_remove,
    M3_BILLBOARD_BEHAVIORS_OT_move,
    M3_INVERSE_KINEMATIC_CHAINS_OT_add,
    M3_INVERSE_KINEMATIC_CHAINS_OT_remove,
    M3_INVERSE_KINEMATIC_CHAINS_OT_move,
    M3_TURRET_BEHAVIORS_OT_add,
    M3_TURRET_BEHAVIORS_OT_remove,
    M3_TURRET_BEHAVIORS_OT_move,
    M3_TURRET_BEHAVIOR_PARTS_OT_add,
    M3_TURRET_BEHAVIOR_PARTS_OT_remove,
    M3_TURRET_BEHAVIOR_PARTS_OT_move,
    ui.M3_PROJECTIONS_OT_add,
    ui.M3_PROJECTIONS_OT_remove,
    ui.M3_PROJECTIONS_OT_move,
    ui.M3_PROJECTIONS_OT_duplicate,
    M3_WARPS_OT_add,
    M3_WARPS_OT_remove,
    M3_WARPS_OT_move,
    M3_WARPS_OT_duplicate,
    M3_TIGHT_HIT_TESTS_OT_selectorcreatebone,
    M3_TIGHT_HIT_TESTS_OT_hittestremove,
    M3_FUZZY_HIT_TESTS_OT_add,
    M3_FUZZY_HIT_TESTS_OT_remove,
    M3_FUZZY_HIT_TESTS_OT_move,
    M3_ATTACHMENT_POINTS_OT_add,
    M3_ATTACHMENT_POINTS_OT_remove,
    M3_ATTACHMENT_POINTS_OT_move,
    ui.ImportPanel,
    ui.M3_OT_quickImport,
    ui.M3_OT_import,
    ui.ExportPanel,
    ui.M3_OT_quickExport,
    ui.M3_OT_export,
    M3_OT_generateBlenderMaterails,
    M3_OT_conertBlenderToM3NormalMap,
    M3_OT_conertM3ToBlenderNormalMap,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.m3_animation_index = bpy.props.IntProperty(update=handleAnimationSequenceIndexChange, default=-1)
    bpy.types.Scene.m3_animations = bpy.props.CollectionProperty(type=M3Animation)
    bpy.types.Scene.m3_material_layer_index = bpy.props.IntProperty()
    bpy.types.Scene.m3_material_references = bpy.props.CollectionProperty(type=cm.M3Material)
    bpy.types.Scene.m3_standard_materials = bpy.props.CollectionProperty(type=M3StandardMaterial)
    bpy.types.Scene.m3_displacement_materials = bpy.props.CollectionProperty(type=M3DisplacementMaterial)
    bpy.types.Scene.m3_composite_materials = bpy.props.CollectionProperty(type=M3CompositeMaterial)
    bpy.types.Scene.m3_terrain_materials = bpy.props.CollectionProperty(type=M3TerrainMaterial)
    bpy.types.Scene.m3_volume_materials = bpy.props.CollectionProperty(type=M3VolumeMaterial)
    bpy.types.Scene.m3_volume_noise_materials = bpy.props.CollectionProperty(type=M3VolumeNoiseMaterial)
    bpy.types.Scene.m3_creep_materials = bpy.props.CollectionProperty(type=M3CreepMaterial)
    bpy.types.Scene.m3_stb_materials = bpy.props.CollectionProperty(type=M3STBMaterial)
    bpy.types.Scene.m3_lens_flare_materials = bpy.props.CollectionProperty(type=M3LensFlareMaterial)
    bpy.types.Scene.m3_buffer_materials = bpy.props.CollectionProperty(type=M3MaterialNode)
    bpy.types.Scene.m3_material_reference_index = bpy.props.IntProperty(default=-1)
    bpy.types.Scene.m3_cameras = bpy.props.CollectionProperty(type=M3Camera)
    bpy.types.Scene.m3_camera_index = bpy.props.IntProperty(update=handleCameraIndexChanged, default=-1)
    bpy.types.Scene.m3_particle_systems = bpy.props.CollectionProperty(type=M3ParticleSystem)
    bpy.types.Scene.m3_particle_system_index = bpy.props.IntProperty(update=handleParticleSystemIndexChanged, default=-1)
    bpy.types.Scene.m3_ribbons = bpy.props.CollectionProperty(type=M3Ribbon)
    bpy.types.Scene.m3_ribbon_index = bpy.props.IntProperty(update=handleRibbonIndexChanged, default=-1)
    bpy.types.Scene.m3_forces = bpy.props.CollectionProperty(type=M3Force)
    bpy.types.Scene.m3_force_index = bpy.props.IntProperty(update=handleForceIndexChanged, default=-1)
    bpy.types.Scene.m3_rigid_bodies = bpy.props.CollectionProperty(type=M3RigidBody)
    bpy.types.Scene.m3_rigid_body_index = bpy.props.IntProperty(update=handleRigidBodyIndexChange, default=-1)
    bpy.types.Scene.m3_lights = bpy.props.CollectionProperty(type=M3Light)
    bpy.types.Scene.m3_light_index = bpy.props.IntProperty(update=handleLightIndexChanged, default=-1)
    bpy.types.Scene.m3_billboard_behaviors = bpy.props.CollectionProperty(type=M3BillboardBehavior)
    bpy.types.Scene.m3_billboard_behavior_index = bpy.props.IntProperty(update=handleBillboardBehaviorIndexChanged, default=-1)
    bpy.types.Scene.m3_ik_chains = bpy.props.CollectionProperty(type=M3InverseKinematicChain)
    bpy.types.Scene.m3_ik_chain_index = bpy.props.IntProperty(default=-1, update=handleIkChainIndexChanged)
    bpy.types.Scene.m3_turret_behaviors = bpy.props.CollectionProperty(type=M3TurretBehavior)
    bpy.types.Scene.m3_turret_behavior_index = bpy.props.IntProperty(default=-1)
    bpy.types.Scene.m3_physics_joint_pivots = bpy.props.BoolProperty(options=set(), default=True, update=handlePhysicsJointPivotDisplay)
    bpy.types.Scene.m3_physics_joints = bpy.props.CollectionProperty(type=M3PhysicsJoint)
    bpy.types.Scene.m3_physics_joint_index = bpy.props.IntProperty(default=-1, update=handlePhysicsJointIndexChanged)
    bpy.types.Scene.m3_projections = bpy.props.CollectionProperty(type=cm.M3GroupProjection)
    bpy.types.Scene.m3_projection_index = bpy.props.IntProperty(update=cm.handleProjectionIndexChanged, default=-1)
    bpy.types.Scene.m3_warps = bpy.props.CollectionProperty(type=M3Warp)
    bpy.types.Scene.m3_warp_index = bpy.props.IntProperty(update=handleWarpIndexChanged, default=-1)
    bpy.types.Scene.m3_attachment_points = bpy.props.CollectionProperty(type=M3AttachmentPoint)
    bpy.types.Scene.m3_attachment_point_index = bpy.props.IntProperty(update=handleAttachmentPointIndexChanged, default=-1)
    bpy.types.Scene.m3_export_options = bpy.props.PointerProperty(type=cm.M3ExportOptions)
    bpy.types.Scene.m3_import_options = bpy.props.PointerProperty(type=cm.M3ImportOptions)
    bpy.types.Scene.m3_bone_visiblity_options = bpy.props.PointerProperty(type=M3BoneVisiblityOptions)
    bpy.types.Scene.m3_visibility_test = bpy.props.PointerProperty(type=M3Boundings)
    bpy.types.Scene.m3_animation_ids = bpy.props.CollectionProperty(type=M3AnimIdData)
    bpy.types.Scene.m3_fuzzy_hit_tests = bpy.props.CollectionProperty(type=M3SimpleGeometricShape)
    bpy.types.Scene.m3_fuzzy_hit_test_index = bpy.props.IntProperty(update=handleFuzzyHitTestIndexChanged, default=-1)
    bpy.types.Scene.m3_tight_hit_test = bpy.props.PointerProperty(type=M3SimpleGeometricShape)
    bpy.types.Mesh.m3_material_name = bpy.props.StringProperty()
    bpy.types.Mesh.m3_physics_mesh = bpy.props.BoolProperty(default=False, description="Mark mesh to be used for physics shape only (not exported).")
    bpy.types.Mesh.m3_sign_group = bpy.props.StringProperty()
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.IMAGE_MT_image.append(menu_func_convertNormalMaps)
    bpy.types.Bone.m3_bind_scale = bpy.props.FloatVectorProperty(default=(1, 1, 1), size=3)
    bpy.types.EditBone.m3_bind_scale = bpy.props.FloatVectorProperty(default=(1, 1, 1), size=3)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.IMAGE_MT_image.remove(menu_func_convertNormalMaps)


if __name__ == "__main__":
    register()
