# Credits and licence

The code below is released under https://www.gnu.org/licenses/gpl-3.0.txt
Author : Mjollna (admin@mjollna.org), 2017-09

Thx gamh for https://bitbucket.org/Shgck/pywmo/ , it helped a lot for structs and other stuff ! :)    

# HOW TO USE : 

The script should run fine in python 2. 

This scripts converts a gltf + bin file (Blender export 2.77a) into m2 + skin for Wow 3.3.5. 

- Don't forget to install the Blender gltf import/export addon from Khronos Group : 
git clone https://github.com/KhronosGroup/glTF-Blender-Exporter.git (it might take some time, repo is ~275Mb)r

Follow this procedure to have textures properly linked : ( https://github.com/KhronosGroup/glTF-Blender-Exporter/blob/master/docs/user.md )

- Open your Blender file.
- Use Cycles engine.
- File menu > *append* > go to the repo folder > pbr_node/glTF2.blend > NodeTree > glTF Metallic Roughness.
(you can use "link" instead of "append", so that your file is lighter, but you won't be able to move/transfer it without losing the material group).
- In the cycles material editor (shift + F3) > add > group > gltfMetallic roughness.
- Link the gltf to surface output.
- Add a texture image, and link it to the base color of the gltf group.

Before exporting : 

- For now, only one texture per mesh is ok.
- Use a single UV island for your model. If more than one island is used, UV mapping & actually the whole model look completely scrambled ingame. Mark seam is ok though.
- You can select smooth shading (object mode) to have nicer normals ingame.
- Work in quads and apply a triangulate modifier just before exporting (wrench icon > modifier > triangulate > apply).

Export options : 
- Select your mesh in object mode.
- File > export > gltf (not glb !)
- export selected only
- apply modifiers
- force maximum indices
- export texture coordinates
- export normals
- export materials
- export animations
- keyframes start with 0

Commandline (be sure to have textures and bin files in the same folder) : 
- python main.py yourfile.gltf world\texturepath\
- argument 1 : input gltf file
- argument 2 : textures path of the output m2.