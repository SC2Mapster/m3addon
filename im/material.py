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
import bpy.types as bt
from .. import shared


def createMaterialForMesh(scene: bt.Scene, mesh: bt.Mesh):
    standardMaterial = shared.getStandardMaterialOrNull(scene, mesh)
    if standardMaterial is None:
        return

    realMaterial = bpy.data.materials.new(standardMaterial.name)
    directoryList = shared.determineTextureDirectoryList(scene)

    realMaterial.use_nodes = True
    tree = realMaterial.node_tree
    tree.links.clear()
    tree.nodes.clear()

    # diffuse
    diffuseLayer = standardMaterial.layers[shared.getLayerNameFromFieldName("diffuseLayer")]
    diffuseTextureNode = shared.createTextureNodeForM3MaterialLayer(mesh, tree, diffuseLayer, directoryList)
    if diffuseTextureNode is not None:
        if diffuseLayer.colorChannelSetting == shared.colorChannelSettingRGBA:
            diffuseTeamColorMixNode = tree.nodes.new("ShaderNodeMixRGB")
            diffuseTeamColorMixNode.blend_type = "MIX"
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

    # normal
    normalMapNode = shared.createNormalMapNode(mesh, tree, standardMaterial, directoryList)

    # specular
    specularLayer = standardMaterial.layers[shared.getLayerNameFromFieldName("specularLayer")]
    specularTextureNode = shared.createTextureNodeForM3MaterialLayer(mesh, tree, specularLayer, directoryList)

    # emissive
    emissiveLayer = standardMaterial.layers[shared.getLayerNameFromFieldName("emissiveLayer")]
    emissiveTextureNode = shared.createTextureNodeForM3MaterialLayer(mesh, tree, emissiveLayer, directoryList)

    # PrincipledBSDF
    shaderBSDF = tree.nodes.new("ShaderNodeBsdfPrincipled")
    shaderBSDF.inputs["Roughness"].default_value = 0.2

    tree.links.new(finalDiffuseColorOutputSocket, shaderBSDF.inputs["Base Color"])
    if normalMapNode is not None:
        tree.links.new(normalMapNode.outputs["Normal"], shaderBSDF.inputs["Normal"])
    if specularTextureNode is not None:
        tree.links.new(specularTextureNode.outputs["Color"], shaderBSDF.inputs["Specular"])
    if emissiveTextureNode is not None:
        tree.links.new(emissiveTextureNode.outputs["Color"], shaderBSDF.inputs["Emission"])

    # output
    outputNode = tree.nodes.new("ShaderNodeOutputMaterial")
    outputNode.location = (500.0, 000.0)
    tree.links.new(shaderBSDF.outputs["BSDF"], outputNode.inputs["Surface"])

    shared.layoutInputNodesOf(tree)

    # Remove old materials:
    while len(mesh.materials) > 0:
        mesh.materials.pop(index=0, update_data=True)

    mesh.materials.append(realMaterial)
