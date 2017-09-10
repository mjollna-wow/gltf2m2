#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" The script should run fine in python 2. 
    
    The code below is released under https://www.gnu.org/licenses/gpl-3.0.txt
    Author : Mjollna (admin@mjollna.org), 2017-09
    
    Thx gamh for https://bitbucket.org/Shgck/pywmo/ , it helped a lot for structs and other stuff ! :)    
    
""" 

import struct
import json
import os
import sys

""" HOW TO USE : 

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

"""

""" GENERIC STUFF 
"""

struct_u32 = struct.Struct("<I")
struct_i = struct.Struct("<i")
struct_f = struct.Struct("<f")
struct_u8 = struct.Struct("<B")
struct_h = struct.Struct("<h")

def _get_u32(f): return struct_u32.unpack(f.read(4))[0]
def _get_f(f): return struct_f.unpack(f.read(4))[0]

""" MODEL CLASS 
"""

class Model(object):
  def __init__(self, name=None, texture=None, vertices=None, normals=None, triangles=None, texture_coords_0=None, mesh_min_bounds=None, mesh_max_bounds=None):
    if name is None:
      self.name = "default_name"
      self.texture = ""
      self.vertices = []
      self.normals = []
      self.triangles = []
      self.texture_coords_0 = []
      self.min_bounds = []
      self.max_bounds = []
    else:
      self.load_mesh(name, texture, vertices, normals, triangles, texture_coords_0, mesh_min_bounds, mesh_max_bounds)
    
  def load_mesh(self, name, texture, vertices, normals, triangles, texture_coords_0, mesh_min_bounds, mesh_max_bounds):
    self.name = name
    self.texture = texture
    self.vertices = vertices
    self.normals = normals
    self.triangles = triangles
    self.texture_coords_0 = texture_coords_0
    self.min_bounds = mesh_min_bounds
    self.max_bounds = mesh_max_bounds

  def make_z_up(self): # idk if I have to move normals too... Do I ?
    # X Y Z -> X -Z Y    
    
    all_x = []
    all_y = []
    all_z = []
    new_vertices_order = []
    
    for v in range (0, len(self.vertices) / 3):
      all_x.append(self.vertices[v * 3])
      all_y.append(self.vertices[v * 3 + 1])
      all_z.append(self.vertices[v * 3 + 2])

    for v in range (0, len(self.vertices) / 3):
      new_vertices_order.append(all_x[v])
      new_vertices_order.append(all_z[v] * -1)
      new_vertices_order.append(all_y[v])
    
    self.vertices = new_vertices_order
    
    y_min_bound = self.min_bounds[1]
    z_min_bound = self.min_bounds[2]
    
    self.min_bounds[1] = z_min_bound * -1
    self.min_bounds[2] = y_min_bound

    y_max_bound = self.max_bounds[1]
    z_max_bound = self.max_bounds[2]
    
    self.max_bounds[1] = z_max_bound * -1
    self.max_bounds[2] = y_max_bound

  def write_m2(self, texture_path):
    
    self.make_z_up()
    
    # Compute the values to be written
    
    transparency_block_size = 20
    timestamp_block_size = 8
    subanim_block_size = 8
    fake_timestamp_size = 4
    
    fake_anim_block = [0, 0, 3333, 0.0, 32, 32767, 0, 0, 0, 150, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1, 0]
    anim_block_size = 64
    
    fake_bone_block = [-1, 0, -1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0.0, 0.0 , 0.0]
    bone_block_size = 88
    
    texture_full_name = texture_path + self.texture[0:-3] + "blp"
    texture_length = int(len(texture_full_name))
    
    keybone_lookup = -1
    
    n_name = len(self.name)
    ofs_name = 304 # start at header size
    global_flags = 0
    n_global_seq = 0
    ofs_global_seq = 0
    n_anims = 1
    ofs_anims = ofs_name + len(self.name) + 1 # string null terminated
    n_anim_lookup = 0
    ofs_anim_lookup = 0
    n_bones = 1
    ofs_bones = ofs_anims + anim_block_size * n_anims
    n_keybone_lookup = 1
    ofs_keybone_lookup = ofs_bones + bone_block_size * n_bones
    n_vertices = (len(self.vertices) / 3) # because vec3
    ofs_vertices = ofs_keybone_lookup + 2 # because keybone_lookup is h
    n_views = 1
    n_colors = 0
    ofs_colors = 0
    n_textures = 1
    ofs_textures = ofs_vertices + 48 * n_vertices
    n_transparency = 1
    ofs_transparency = ofs_textures + 16 + len(texture_full_name) + 1 # string null terminated
    n_texture_animations = 0
    ofs_texture_animations = 0
    n_tex_replace = 1
    ofs_tex_replace = ofs_transparency + transparency_block_size + timestamp_block_size + subanim_block_size + fake_timestamp_size + 2
    n_render_flags = 1
    ofs_render_flags = ofs_tex_replace + 2
    n_bone_lookup_table = 4
    ofs_bone_lookup_table = ofs_render_flags + 4
    n_tex_lookup = 1
    ofs_tex_lookup = ofs_bone_lookup_table + n_bone_lookup_table * 2
    n_tex_units = 1
    ofs_tex_units = ofs_tex_lookup + 2
    n_trans_lookup = 1
    ofs_trans_lookup = ofs_tex_units + 2
    n_tex_anim_lookup = 1
    ofs_tex_anim_lookup = ofs_trans_lookup + 2
    bounding_lower_x = self.min_bounds[0]
    bounding_lower_y = self.min_bounds[1]
    bounding_lower_z = self.min_bounds[2]
    bounding_upper_x = self.max_bounds[0]
    bounding_upper_y = self.max_bounds[1]
    bounding_upper_z = self.max_bounds[2]
    bounding_radius = 3.0 # TODO : get bounds
    collisions_lower_x = self.min_bounds[0] # TODO
    collisions_lower_y = self.min_bounds[1] # TODO
    collisions_lower_z = self.min_bounds[2] # TODO
    collisions_upper_x = self.max_bounds[0] # TODO
    collisions_upper_y = self.max_bounds[1] # TODO
    collisions_upper_z = self.max_bounds[2] # TODO
    collisions_radius = bounding_radius # TODO
    n_bounding_triangles = 0
    ofs_bounding_triangles = 0
    n_bounding_vertices = 0
    ofs_bounding_vertices = 0
    n_bounding_normals = 0
    ofs_bounding_normals = 0
    n_attachments = 0
    ofs_attachments = 0
    n_attach_lookup = 0
    ofs_attach_lookup = 0
    n_events = 0
    ofs_events = 0
    n_lights = 0
    ofs_lights = 0
    n_cameras = 0
    ofs_cameras = 0
    n_camera_lookup = 0
    ofs_camera_lookup = 0
    n_ribbon_emitters = 0
    ofs_ribbon_emitters = 0
    n_particle_emitters = 0
    ofs_particle_emitters = 0    
    
    transparency_block = [0, -1, 1, ofs_transparency + transparency_block_size, 1, ofs_transparency + transparency_block_size + timestamp_block_size]
    timestamp_block = [1, ofs_transparency + transparency_block_size + timestamp_block_size + subanim_block_size]
    subanim_block = [1, ofs_transparency + transparency_block_size + timestamp_block_size + subanim_block_size + fake_timestamp_size]

    fake_timestamp_value = 0
    fake_subanim_value = 32767
    
    filename = self.name + ".m2"
    with open(filename, "wb") as out_file:
      
      # The header
      
      out_file.write(struct_u32.pack(808600653))
      out_file.write(struct_u32.pack(264))
      
      out_file.write(struct_u32.pack(n_name))
      out_file.write(struct_u32.pack(ofs_name))
      
      out_file.write(struct_u32.pack(global_flags))
      
      out_file.write(struct_u32.pack(n_global_seq))
      if n_global_seq == 0:
        out_file.write(struct_u32.pack(0))
      else:
        out_file.write(struct_u32.pack(ofs_global_seq))
      
      out_file.write(struct_u32.pack(n_anims))
      out_file.write(struct_u32.pack(ofs_anims))

      out_file.write(struct_u32.pack(n_anim_lookup))
      if n_anim_lookup == 0:      
        out_file.write(struct_u32.pack(ofs_anim_lookup))
      else:
        out_file.write(struct_u32.pack(ofs_anim_lookup))        

      out_file.write(struct_u32.pack(n_bones))
      out_file.write(struct_u32.pack(ofs_bones))

      out_file.write(struct_u32.pack(n_keybone_lookup))
      out_file.write(struct_u32.pack(ofs_keybone_lookup))
      
      out_file.write(struct_u32.pack(n_vertices))
      out_file.write(struct_u32.pack(ofs_vertices))      

      out_file.write(struct_u32.pack(n_views))

      out_file.write(struct_u32.pack(n_colors))
      out_file.write(struct_u32.pack(ofs_colors))

      out_file.write(struct_u32.pack(n_textures))
      out_file.write(struct_u32.pack(ofs_textures))

      out_file.write(struct_u32.pack(n_transparency))
      out_file.write(struct_u32.pack(ofs_transparency))

      out_file.write(struct_u32.pack(n_texture_animations))
      out_file.write(struct_u32.pack(ofs_texture_animations))

      out_file.write(struct_u32.pack(n_tex_replace))
      out_file.write(struct_u32.pack(ofs_tex_replace))

      out_file.write(struct_u32.pack(n_render_flags))
      out_file.write(struct_u32.pack(ofs_render_flags))

      out_file.write(struct_u32.pack(n_bone_lookup_table))
      out_file.write(struct_u32.pack(ofs_bone_lookup_table))

      out_file.write(struct_u32.pack(n_tex_lookup))
      out_file.write(struct_u32.pack(ofs_tex_lookup))

      out_file.write(struct_u32.pack(n_tex_units))
      out_file.write(struct_u32.pack(ofs_tex_units))

      out_file.write(struct_u32.pack(n_trans_lookup))
      out_file.write(struct_u32.pack(ofs_trans_lookup))

      out_file.write(struct_u32.pack(n_tex_anim_lookup))
      out_file.write(struct_u32.pack(ofs_tex_anim_lookup))

      out_file.write(struct_f.pack(bounding_lower_x))
      out_file.write(struct_f.pack(bounding_lower_y))
      out_file.write(struct_f.pack(bounding_lower_z))      

      out_file.write(struct_f.pack(bounding_upper_x))
      out_file.write(struct_f.pack(bounding_upper_y))
      out_file.write(struct_f.pack(bounding_upper_z))

      out_file.write(struct_f.pack(bounding_radius))

      out_file.write(struct_f.pack(collisions_lower_x))
      out_file.write(struct_f.pack(collisions_lower_y))
      out_file.write(struct_f.pack(collisions_lower_z))      

      out_file.write(struct_f.pack(collisions_upper_x))
      out_file.write(struct_f.pack(collisions_upper_y))
      out_file.write(struct_f.pack(collisions_upper_z))

      out_file.write(struct_f.pack(collisions_radius))
      
      out_file.write(struct_f.pack(n_bounding_triangles))
      out_file.write(struct_f.pack(ofs_bounding_triangles))

      out_file.write(struct_f.pack(n_bounding_vertices))
      out_file.write(struct_f.pack(ofs_bounding_vertices))

      out_file.write(struct_f.pack(n_bounding_normals))
      out_file.write(struct_f.pack(ofs_bounding_normals))

      out_file.write(struct_f.pack(n_attachments))
      out_file.write(struct_f.pack(ofs_attachments))

      out_file.write(struct_f.pack(n_attach_lookup))
      out_file.write(struct_f.pack(ofs_attach_lookup))

      out_file.write(struct_f.pack(n_events))
      out_file.write(struct_f.pack(ofs_events))

      out_file.write(struct_f.pack(n_lights))
      out_file.write(struct_f.pack(ofs_lights))

      out_file.write(struct_f.pack(n_cameras))
      out_file.write(struct_f.pack(ofs_cameras))

      out_file.write(struct_f.pack(n_camera_lookup))
      out_file.write(struct_f.pack(ofs_camera_lookup))

      out_file.write(struct_f.pack(n_ribbon_emitters))
      out_file.write(struct_f.pack(ofs_ribbon_emitters))      

      out_file.write(struct_f.pack(n_particle_emitters))
      out_file.write(struct_f.pack(ofs_particle_emitters))
      
      # After the header
      
      # [global sequence : can be skipped if 0 in header]
      
      out_file.write(self.name)
      out_file.write(struct_u8.pack(0)) # string null terminated

      out_file.write(struct_h.pack(fake_anim_block[0]))
      out_file.write(struct_h.pack(fake_anim_block[1]))
      out_file.write(struct_u32.pack(fake_anim_block[2]))
      out_file.write(struct_f.pack(fake_anim_block[3]))
      out_file.write(struct_u32.pack(fake_anim_block[4]))
      out_file.write(struct_h.pack(fake_anim_block[5]))
      out_file.write(struct_h.pack(fake_anim_block[6]))
      out_file.write(struct_u32.pack(fake_anim_block[7]))
      out_file.write(struct_u32.pack(fake_anim_block[8]))
      out_file.write(struct_u32.pack(fake_anim_block[9]))      
      out_file.write(struct_f.pack(fake_anim_block[10]))
      out_file.write(struct_f.pack(fake_anim_block[11]))
      out_file.write(struct_f.pack(fake_anim_block[12]))
      out_file.write(struct_f.pack(fake_anim_block[13]))
      out_file.write(struct_f.pack(fake_anim_block[14]))
      out_file.write(struct_f.pack(fake_anim_block[15]))
      out_file.write(struct_f.pack(fake_anim_block[16]))
      out_file.write(struct_h.pack(fake_anim_block[17]))
      out_file.write(struct_h.pack(fake_anim_block[18]))
      
      out_file.write(struct_i.pack(fake_bone_block[0]))
      out_file.write(struct_u32.pack(fake_bone_block[1]))
      out_file.write(struct_h.pack(fake_bone_block[2]))
      out_file.write(struct_h.pack(fake_bone_block[3]))
      out_file.write(struct_h.pack(fake_bone_block[4]))
      out_file.write(struct_h.pack(fake_bone_block[5]))      
      out_file.write(struct_h.pack(fake_bone_block[6]))
      out_file.write(struct_h.pack(fake_bone_block[7]))
      out_file.write(struct_u32.pack(fake_bone_block[8]))
      out_file.write(struct_u32.pack(fake_bone_block[9]))
      out_file.write(struct_u32.pack(fake_bone_block[10]))
      out_file.write(struct_u32.pack(fake_bone_block[11]))      
      out_file.write(struct_h.pack(fake_bone_block[12]))
      out_file.write(struct_h.pack(fake_bone_block[13]))
      out_file.write(struct_u32.pack(fake_bone_block[14]))
      out_file.write(struct_u32.pack(fake_bone_block[15]))
      out_file.write(struct_u32.pack(fake_bone_block[16]))
      out_file.write(struct_u32.pack(fake_bone_block[17]))      
      out_file.write(struct_h.pack(fake_bone_block[18]))
      out_file.write(struct_h.pack(fake_bone_block[19]))
      out_file.write(struct_u32.pack(fake_bone_block[20]))
      out_file.write(struct_u32.pack(fake_bone_block[21]))
      out_file.write(struct_u32.pack(fake_bone_block[22]))
      out_file.write(struct_u32.pack(fake_bone_block[23]))      
      out_file.write(struct_f.pack(fake_bone_block[24]))
      out_file.write(struct_f.pack(fake_bone_block[25]))
      out_file.write(struct_f.pack(fake_bone_block[26]))
      
      out_file.write(struct_h.pack(keybone_lookup))
      
      for v in range (0, (len(self.vertices) / 3)):
        # 1 vertex : 
        out_file.write(struct_f.pack(self.vertices[v * 3])) # pos
        out_file.write(struct_f.pack(self.vertices[v * 3 + 1]))
        out_file.write(struct_f.pack(self.vertices[v * 3 + 2]))
        out_file.write(struct_u8.pack(255)) # bone weight
        out_file.write(struct_u8.pack(0))
        out_file.write(struct_u8.pack(0))
        out_file.write(struct_u8.pack(0))
        out_file.write(struct_u8.pack(0)) # bone indice
        out_file.write(struct_u8.pack(0))
        out_file.write(struct_u8.pack(0))
        out_file.write(struct_u8.pack(0))
        out_file.write(struct_f.pack(self.normals[v * 3])) # normals (normalize them ?)
        out_file.write(struct_f.pack(self.normals[v * 3 + 1]))
        out_file.write(struct_f.pack(self.normals[v * 3 + 2]))
        out_file.write(struct_f.pack(self.texture_coords_0[v * 2])) # tex coords 0
        out_file.write(struct_f.pack(self.texture_coords_0[v * 2 + 1]))
        out_file.write(struct_f.pack(0.0)) # tex coords 1
        out_file.write(struct_f.pack(0.0))
      
      out_file.write(struct_u32.pack(0)) # texture type
      out_file.write(struct_u32.pack(0)) # texture flags
      out_file.write(struct_u32.pack(texture_length)) # texture filename length
      out_file.write(struct_u32.pack(ofs_textures + 4 * 4))
      out_file.write(texture_full_name)
      out_file.write(struct_u8.pack(0)) # string null terminated

      out_file.write(struct_h.pack(transparency_block[0]))
      out_file.write(struct_h.pack(transparency_block[1]))
      out_file.write(struct_u32.pack(transparency_block[2]))
      out_file.write(struct_u32.pack(transparency_block[3]))
      out_file.write(struct_u32.pack(transparency_block[4]))
      out_file.write(struct_u32.pack(transparency_block[5]))
      
      out_file.write(struct_u32.pack(timestamp_block[0]))
      out_file.write(struct_u32.pack(timestamp_block[1]))
      
      out_file.write(struct_u32.pack(subanim_block[0]))
      out_file.write(struct_u32.pack(subanim_block[1]))
      
      out_file.write(struct_u32.pack(fake_timestamp_value))
      out_file.write(struct_h.pack(fake_subanim_value))

      out_file.write(struct_h.pack(0)) # texreplace short 0
      out_file.write(struct_h.pack(0)) # renderflags 0
      out_file.write(struct_h.pack(0)) # blending mode

      out_file.write(struct_h.pack(0)) # bone lookup table
      out_file.write(struct_h.pack(0)) # bone lookup table      
      out_file.write(struct_h.pack(0)) # bone lookup table
      out_file.write(struct_h.pack(0)) # bone lookup table
      
      out_file.write(struct_h.pack(0)) # texlookuptable 0
      out_file.write(struct_h.pack(0)) # texunitlookuptable 0
      out_file.write(struct_h.pack(0)) # translookuptable 0
      out_file.write(struct_h.pack(-1)) # texanimlookuptable -1
      
      # [bounding triangles (6 floats)]
      # [bounding vertices (6 floats)]
      # [bounding normals (6 floats)]

    skinfilename = self.name + "00.skin"
    with open(skinfilename, "wb") as out_skin_file:
      
      submeshes_fake_block_size = 48
      
      submeshes_fake_block = [0, 0, 0, len(self.vertices) / 3, min(self.triangles), len(self.triangles), n_bones, 0, 1, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, bounding_radius]      
      
      texture_units_block = [16, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0]
      
      n_indices = len(self.vertices) / 3
      ofs_indices = 48 # start at skin header size
      n_triangles = len(self.triangles)
      ofs_triangles = ofs_indices + n_indices * 2
      n_properties = n_indices
      ofs_properties = ofs_triangles + (len(self.triangles) * 2)
      n_submeshes = 1
      ofs_submeshes = ofs_properties + n_properties * 4#(len(self.triangles) * 4)
      n_texture_units = 1
      ofs_texture_units = ofs_submeshes + submeshes_fake_block_size
      lod = 0      
      
      out_skin_file.write(struct_u32.pack(1313426259))
      out_skin_file.write(struct_u32.pack(n_indices))
      out_skin_file.write(struct_u32.pack(ofs_indices))
      out_skin_file.write(struct_u32.pack(n_triangles))
      out_skin_file.write(struct_u32.pack(ofs_triangles))
      out_skin_file.write(struct_u32.pack(n_properties))
      out_skin_file.write(struct_u32.pack(ofs_properties))
      out_skin_file.write(struct_u32.pack(n_submeshes))
      out_skin_file.write(struct_u32.pack(ofs_submeshes))
      out_skin_file.write(struct_u32.pack(n_texture_units))
      out_skin_file.write(struct_u32.pack(ofs_texture_units))      
      out_skin_file.write(struct_u32.pack(lod))
      
      for i in range (0, n_indices):
        out_skin_file.write(struct_h.pack(i))
      
      for tri in self.triangles:
        out_skin_file.write(struct_h.pack(tri))
      
      for i in range (0, n_properties):
        for i in range (0, 4):
          out_skin_file.write(struct_u8.pack(0))      
      
      out_skin_file.write(struct_h.pack(submeshes_fake_block[0]))
      out_skin_file.write(struct_h.pack(submeshes_fake_block[1]))
      out_skin_file.write(struct_h.pack(submeshes_fake_block[2]))
      out_skin_file.write(struct_h.pack(submeshes_fake_block[3]))
      out_skin_file.write(struct_h.pack(submeshes_fake_block[4]))      
      out_skin_file.write(struct_h.pack(submeshes_fake_block[5]))
      out_skin_file.write(struct_h.pack(submeshes_fake_block[6]))
      out_skin_file.write(struct_h.pack(submeshes_fake_block[7]))
      out_skin_file.write(struct_h.pack(submeshes_fake_block[8]))
      out_skin_file.write(struct_h.pack(submeshes_fake_block[9]))      
      out_skin_file.write(struct_f.pack(submeshes_fake_block[10]))
      out_skin_file.write(struct_f.pack(submeshes_fake_block[11]))
      out_skin_file.write(struct_f.pack(submeshes_fake_block[12]))
      out_skin_file.write(struct_f.pack(submeshes_fake_block[13]))
      out_skin_file.write(struct_f.pack(submeshes_fake_block[14]))
      out_skin_file.write(struct_f.pack(submeshes_fake_block[15]))
      out_skin_file.write(struct_f.pack(submeshes_fake_block[16]))      

      out_skin_file.write(struct_u8.pack(texture_units_block[0]))
      out_skin_file.write(struct_u8.pack(texture_units_block[1]))
      out_skin_file.write(struct_h.pack(texture_units_block[2]))
      out_skin_file.write(struct_h.pack(texture_units_block[3]))
      out_skin_file.write(struct_h.pack(texture_units_block[4]))      
      out_skin_file.write(struct_h.pack(texture_units_block[5]))
      out_skin_file.write(struct_h.pack(texture_units_block[6]))
      out_skin_file.write(struct_h.pack(texture_units_block[7]))
      out_skin_file.write(struct_h.pack(texture_units_block[8]))
      out_skin_file.write(struct_h.pack(texture_units_block[9]))
      out_skin_file.write(struct_h.pack(texture_units_block[10]))
      out_skin_file.write(struct_h.pack(texture_units_block[11]))
      out_skin_file.write(struct_h.pack(texture_units_block[12]))      
      
    print("Files " + self.name + ".m2 and " + self.name + "00.skin saved")

""" LOADING INFO FROM FILES
"""

def load_models(path):
  models_list = []
  with open(path, "rb") as model_file:  
    gltf = json.load(model_file)
    
    mesh_number = len(gltf.get('meshes', [])) - 1
    
    for mesh in gltf.get('meshes', []):
      current_mesh_info = []
      mesh_uri = gltf.get('buffers', [])[mesh_number]['uri']
      mesh_texture = gltf.get('images', [])[mesh_number]['uri']
      mesh_indices_location = mesh['primitives'][0]['indices']
      mesh_position_location = mesh['primitives'][0]['attributes']['POSITION']
      mesh_normal_location = mesh['primitives'][0]['attributes']['NORMAL']
      mesh_texcoord0_location = mesh['primitives'][0]['attributes']['TEXCOORD_0']
      
      for buffer_view in gltf.get('bufferViews', []): 
        if buffer_view['buffer'] == mesh_number:
          current_mesh_info.append(buffer_view)

      mesh_max_bounds = gltf.get('accessors', [])[mesh_position_location]['max']
      mesh_min_bounds = gltf.get('accessors', [])[mesh_position_location]['min']

      vertices = []
      normals = []
      triangles = []
      texture_coords_0 = []
      how_many = 0
      
      with open(mesh_uri, "rb") as bin_file: # check system path, etc.
        # Get vertices
        bin_file.seek(current_mesh_info[mesh_position_location]['byteLength'])
        grab = bin_file.tell()
        bin_file.seek(current_mesh_info[mesh_position_location]['byteOffset'])
        for i in range (0, grab / 4) :
          vertices.append(_get_f(bin_file))
        
        # Get normals
        bin_file.seek(current_mesh_info[mesh_normal_location]['byteLength'])
        grab = bin_file.tell()
        bin_file.seek(current_mesh_info[mesh_normal_location]['byteOffset'])
        for i in range (0, grab / 4) :
          normals.append(_get_f(bin_file))
        
        # Get UV
        bin_file.seek(current_mesh_info[mesh_texcoord0_location]['byteLength'])
        grab = bin_file.tell()
        bin_file.seek(current_mesh_info[mesh_texcoord0_location]['byteOffset'])
        for i in range (0, grab / 4) :
          texture_coords_0.append(_get_f(bin_file))
        
        # Get indices
        bin_file.seek(current_mesh_info[mesh_indices_location]['byteLength'])
        grab = bin_file.tell()
        bin_file.seek(current_mesh_info[mesh_indices_location]['byteOffset'])
        for i in range (0, grab / 4) :
          triangles.append(_get_u32(bin_file))
      
      models_list.append( Model(mesh['name'], mesh_texture, vertices, normals, triangles, texture_coords_0, mesh_min_bounds, mesh_max_bounds) )
      mesh_number = mesh_number - 1
  return models_list

""" MAIN STUFF 
"""

# load, write to m2, quit.

scene_gltf_name = "pigcube.gltf" # default name for testing.
m2_texture_path = "world\\astro\\" # default name for testing.

# os.getcwd()

if len(sys.argv) > 1:
  scene_gltf_name = sys.argv[1]
if len(sys.argv) > 2:  
  m2_texture_path = sys.argv[2]
  
all_models = load_models(scene_gltf_name) # loading meshes from a gltf scene.

#print(all_models[0].name)
#print(all_models[0].texture)
#print(all_models[0].vertices)
#print(all_models[0].normals)
#print(all_models[0].texture_coords_0)
#print(all_models[0].triangles)
#print(all_models[0].min_bounds)
#print(all_models[0].max_bounds)

all_models[0].write_m2(m2_texture_path)
