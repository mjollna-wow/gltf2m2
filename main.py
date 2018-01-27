#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" The script should run fine in python 2. 
    
    The code below is released under https://www.gnu.org/licenses/gpl-3.0.txt
    Author : Mjollna (admin@mjollna.org), 2018-01
    
    Thx gamh for https://bitbucket.org/Shgck/pywmo/ , it helped a lot for structs and other stuff ! :)
    And thanks a lot to Kyssah and Zhao for the help on quaternions.
    
""" 

import struct
import json
import os
import sys

""" HOW TO USE (please read, that'll save you time later ! :) ) : 

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
    
    About animations : 
    - For now, only animations t/(r)/s of the whole model is supported. No support for bones.
    - To get rotations right, set linear interpolation between F-Curves (keyframes). You can set that by default in Blender (User pref > Editing > Nw F-Curve defaults > Interpolation > Linear). Bezier interpolation in Blender + in M2 bones makes weird results.
    - For better results, keep the same total length for t/r/s animations. (The longest one is picked up by the script to fit global_sequence field).
    - Normal scaling is 1.0, so 0.0 makes the model invisible on the axes with 0.0.
    - Adding scaling animations makes the model invisible in Noggit 3.1222 (SDL), so it might be easier to add scaling animations at the last moment on your edit. When inserting a keyframe in Blender (i), you can selest LocRot instead of LocRotScale to avoid the problem temporarily.
    - There is a problem in make_z_up() function with quaternions, which I cannot fix because I don't understand enough maths. Since the function turns the whole model, rotations probably need to be corrected as well. I've commented my failed attempts at making this right, so rotations are not taken into account in make_z_up() for the time being.
    
    Before exporting : 
    - For now, only one texture per mesh is ok.
    - If you use more than a single UV island for your model, see around line 679 (texture flags) to put 3 instead of 0 for wrap_x and wrap_y. If more than one island is used, without this option UV mapping & actually the whole model have a chance to look completely scrambled ingame. Mark seam is ok though.
    - You can select smooth shading (object mode) to have nicer normals ingame.
    - Work in quads and apply a triangulate modifier just before exporting (wrench icon > modifier > triangulate > apply).
    - Use a single mesh for now. The name of the M2 is the name given to the mesh in Blender.
    
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
    - export within playback range
    - keyframes start with 0
    
    Commandline (be sure to have textures and bin files in the same folder) : 
    - python main.py yourfile.gltf world\texturepath\
    - argument 1 : input gltf file
    - argument 2 : textures path of the output m2.
    Example : python main.py murloc_01.gltf "world\murloc\\"

"""

""" GENERIC STUFF 
"""

struct_u32 = struct.Struct("<I")
struct_i = struct.Struct("<i")
struct_f = struct.Struct("<f")
struct_u8 = struct.Struct("<B")
struct_h = struct.Struct("<h") # signed short
struct_H = struct.Struct("<H") # unsigned short

def _get_u32(f): return struct_u32.unpack(f.read(4))[0]
def _get_f(f): return struct_f.unpack(f.read(4))[0]

def _quat_float_to_short(f):
    value = f
    if (value > 0):
      value = value * 32767.0 - 32768.0
    else: 
      value = value * 32767.0 + 32768.0
    #value = round(value)
    #if value == 32768.0: value = 32767.0 # sometimes rounding messes the values up a little
    return value

""" MODEL CLASS
"""

class Model(object):
    def __init__(self, name=None, texture=None, vertices=None, normals=None, triangles=None, texture_coords_0=None, mesh_min_bounds=None, mesh_max_bounds=None, translation_ts=None, translation_values=None, rotation_ts=None, rotation_values=None, scaling_ts=None, scaling_values=None):
        if name is None:
            self.name = "default_name"
            self.texture = ""
            self.vertices = []
            self.normals = []
            self.triangles = []
            self.texture_coords_0 = []
            self.min_bounds = []
            self.max_bounds = []
            self.translation_ts = []
            self.translation_values = []
            self.rotation_ts = []
            self.rotation_values = []
            self.scaling_ts = []
            self.scaling_values = []            
        else:
            self.load_mesh(name, texture, vertices, normals, triangles, texture_coords_0, mesh_min_bounds, mesh_max_bounds, translation_ts, translation_values, rotation_ts, rotation_values, scaling_ts, scaling_values)
      
    def load_mesh(self, name, texture, vertices, normals, triangles, texture_coords_0, mesh_min_bounds, mesh_max_bounds, translation_ts, translation_values, rotation_ts, rotation_values, scaling_ts, scaling_values):
        self.name = name
        self.texture = texture
        self.vertices = vertices
        self.normals = normals
        self.triangles = triangles
        self.texture_coords_0 = texture_coords_0
        self.min_bounds = mesh_min_bounds
        self.max_bounds = mesh_max_bounds
        self.translation_ts = translation_ts
        self.translation_values = translation_values
        self.rotation_ts = rotation_ts
        self.rotation_values = rotation_values
        self.scaling_ts = scaling_ts
        self.scaling_values = scaling_values

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

        all_tr_x = []
        all_tr_y = []
        all_tr_z = []
        new_tr_order = []
        
        for v in range (0, len(self.translation_values)):
            all_tr_x.append(self.translation_values[v][0])
            all_tr_y.append(self.translation_values[v][1])
            all_tr_z.append(self.translation_values[v][2])

        for v in range (0, len(self.translation_values)):
            new_tr_order.append( [] )
            new_tr_order[v].append(all_tr_x[v])
            new_tr_order[v].append(all_tr_z[v] * -1)
            new_tr_order[v].append(all_tr_y[v])
        
        self.translation_values = new_tr_order
        
        # TODO : for rotations, swapping Y Z > -Z Y has a huge probability to make the animation directions go wild. *sigh* Quaternions...
        
        '''

        all_ro_x = []
        all_ro_y = []
        all_ro_z = []
        all_ro_w = []
        new_ro_order = []
        
        for v in range (0, len(self.rotation_values)):
            all_ro_x.append(self.rotation_values[v][0])
            all_ro_y.append(self.rotation_values[v][1])
            all_ro_z.append(self.rotation_values[v][2])
            all_ro_w.append(self.rotation_values[v][3])

        for v in range (0, len(self.rotation_values)):
            new_ro_order.append( [] )
            new_ro_order[v].append(all_ro_x[v])
            new_ro_order[v].append(all_ro_z[v] * -1)
            new_ro_order[v].append(all_ro_y[v])
            new_ro_order[v].append(all_ro_w[v])
        
        
        for v in range (0, len(new_ro_order)):
            for j in range (0, 4):
                if new_ro_order[v][j] == 32768.0: new_ro_order[v][j] = 32767.0
                if new_ro_order[v][j] == -32767.0: new_ro_order[v][j] = -32768.0
        
        # We make sure to keep the first and last value fixed, to make sure the animation loops right.
        new_ro_order[0] = [32767, 32767, 32767, -1]
        new_ro_order[ len(new_ro_order) - 1 ] = [-32768, -32768, -32768, 0]
        
        print(self.rotation_values)
        
        self.rotation_values = new_ro_order

        print(self.rotation_values)
        
        '''

        all_sc_x = []
        all_sc_y = []
        all_sc_z = []
        new_sc_order = []
        
        for v in range (0, len(self.scaling_values)):
            all_sc_x.append(self.scaling_values[v][0])
            all_sc_y.append(self.scaling_values[v][1])
            all_sc_z.append(self.scaling_values[v][2])

        for v in range (0, len(self.scaling_values)):
            new_sc_order.append( [] )
            new_sc_order[v].append(all_sc_x[v])
            new_sc_order[v].append(all_sc_z[v]) # scaling can't be * -1, I guess
            new_sc_order[v].append(all_sc_y[v])
        
        self.scaling_values = new_sc_order

    def write_m2(self, texture_path):
      
        self.make_z_up() # TODO : for now, if you have a model that rotates, just comment the function to avoid quaternions mess.
      
        # Compute the values to be written
        
        transparency_block_size = 20
        timestamp_block_size = 8
        subanim_block_size = 8
        fake_timestamp_size = 4
        
        # TODO : change these ?
        anim_lower_x = 0.0
        anim_lower_y = 0.0
        anim_lower_z = 0.0
        anim_upper_x = 0.0
        anim_upper_y = 0.0
        anim_upper_z = 0.0
        anim_radius = 0.0
        
        fake_anim_block = [0, 0, 3333, 0.0, 32, 32767, 0, 0, 0, 150, anim_lower_x, anim_lower_y, anim_lower_z, anim_upper_x, anim_upper_y, anim_upper_z, anim_radius, -1, 0]
        anim_block_size = 64
        
        fake_bone_block = [-1, 0, -1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0.0, 0.0 , 0.0]
        bone_block_size = 88 # TODO : * n_bones ?

        ofs_temp = 0 # temp value

        texture_full_name = texture_path + self.texture[0:-3] + "blp"
        texture_length = int(len(texture_full_name))
        
        keybone_lookup = -1
        
        time_tr = 0
        if ( len(self.translation_ts) > 0): time_tr = max(self.translation_ts)
        time_ro = 0
        if ( len(self.rotation_ts) > 0): time_ro = max(self.rotation_ts)
        time_sc = 0
        if ( len(self.scaling_ts) > 0): time_sc = max(self.scaling_ts)
        global_seq = max( time_tr, time_ro, time_sc )
        
        n_name = len(self.name)
        ofs_name = 304 # start at header size
        global_flags = 0
        n_global_seq = 1 # TODO : get real number of sequences (it's ok to have a sequence leading to an empty offset if there's no animation)
        ofs_global_seq = ofs_name + n_name + 1 # string null terminated
        n_anims = 1
        ofs_anims = ofs_global_seq + 4
        n_anim_lookup = 0
        ofs_anim_lookup = 0
        n_bones = 1
        ofs_bones = ofs_anims + anim_block_size * n_anims
        
        # bone start
        keybone_id = -1
        bone_flags = 512
        parent_bone = -1
        bone_unk1 = 0
        bone_unk2 = 55672
        bone_unk3 = 58916

        # for no animations, 0 in first slot is sufficient, the rest of the animation can stay. Ugly but handy.
        t1 = [len(self.translation_ts), 0] 
        t2 = [len(self.translation_values), 0]
        r1 = [len(self.rotation_ts), 0]
        r2 = [len(self.rotation_values), 0]
        s1 = [len(self.scaling_ts), 0]
        s2 = [len(self.scaling_values), 0]
        
        ofs_t1 = ofs_bones + bone_block_size # start after bone block
        ofs_t2 = ofs_t1 + (len(t1) * 4)
        ofs_r1 = ofs_t2 + (len(t2) * 4)
        ofs_r2 = ofs_r1 + len(r1) * 4

        ofs_s1 = ofs_r2 + len(r2) * 4
        ofs_s2 = ofs_s1 + len(s1) * 4

        t1_1 = self.translation_ts
        t2_1 = self.translation_values

        r1_1 = self.rotation_ts
        r2_1 = self.rotation_values
        
        s1_1 = self.scaling_ts
        s2_1 = self.scaling_values
        
        t1[1] = ofs_s2 + len(s2) * 4
        t2[1] = t1[1] + len(t1_1) * 4
        r1[1] = t2[1] + len(t2_1) * 3 * 4
        r2[1] = r1[1] + len(r1_1) * 4
        s1[1] = r2[1] + len(r2_1) * 4 * 2
        s2[1] = s1[1] + len(s1_1) * 4
        
        global_seq_id = 0 # all the anims must have the same ID to be combined
        
        # TODO : change that later to allow multiple keyframe pairs
        has_tr = 0
        if t1[0] != 0: has_tr = 1
        has_ro = 0
        if r1[0] != 0: has_ro = 1
        has_sc = 0
        if s1[0] != 0: has_sc = 1
        
        tr_block = [1, global_seq_id, has_tr, ofs_t1, has_tr, ofs_t2]
        ro_block = [1, global_seq_id, has_ro, ofs_r1, has_ro, ofs_r2]    
        sc_block = [1, global_seq_id, has_sc, ofs_s1, has_sc, ofs_s2]
        
        bone_vector_pivot = [0.0, 0.0, 0.0]
        
        n_keybone_lookup = 1
        ofs_keybone_lookup = s2[1] + len(s2_1) * 4 * 3
        n_vertices = (len(self.vertices) / 3)
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

        """ TODO : Let's see that later, vertices order is totally wrong
        # collisions : instead of a generic cube around the model, it would be better to import a custom bounding box.

        collisions_triangles = [ [0, 1, 2], [2, 3, 0], [4, 5, 6], [6, 7, 4], [0, 3, 5], [5, 4, 0], [3, 2, 6], [6, 5, 3], [2, 1, 7], [7, 6, 2], [1, 0, 4], [4, 7, 1] ]
        
        collisions_vertices = [
            [-1 * collisions_lower_x, collisions_lower_y, -1 * collisions_lower_z], # REF LOWER
            [collisions_lower_x, collisions_lower_y, -1 * collisions_lower_z],
            [-1 * collisions_lower_x, collisions_lower_y, collisions_lower_z],
            [-1 * collisions_lower_x, -1 * collisions_lower_y, collisions_lower_z],

            [collisions_upper_x, -1 * collisions_upper_y, -1 * collisions_upper_z],
            [-1 * collisions_upper_x, -1 * collisions_upper_y, -1 * collisions_upper_z],
            [collisions_upper_x, -1 * collisions_upper_y, collisions_upper_z], # REF UPPER
            [collisions_upper_x, collisions_upper_y,  collisions_upper_z]
        ]

        collisions_normals = [ [0, 0, -1], [0, 0, -1], [0, 0, 1], [0, 0, 1], [1, 0, 0], [1, 0, 0], [0, 1, 0], [0, 1, 0], [-1, 0, 0], [-1, 0, 0], [0, -1, 0], [0, -1, 0] ]
        """

        n_bounding_triangles = 0 # len(collisions_triangles)
        ofs_bounding_triangles = 0 # ofs_tex_anim_lookup + 2
        n_bounding_vertices = 0 # len(collisions_vertices)
        ofs_bounding_vertices = 0 # ofs_bounding_triangles + n_bounding_triangles * 2 * 3
        n_bounding_normals = 0 # len(collisions_normals)
        ofs_bounding_normals = 0 # ofs_bounding_vertices + n_bounding_vertices * 3 * 4
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
            
            out_file.write(struct_u32.pack(n_bounding_triangles))
            out_file.write(struct_u32.pack(ofs_bounding_triangles))

            out_file.write(struct_u32.pack(n_bounding_vertices))
            out_file.write(struct_u32.pack(ofs_bounding_vertices))

            out_file.write(struct_u32.pack(n_bounding_normals))
            out_file.write(struct_u32.pack(ofs_bounding_normals))

            out_file.write(struct_u32.pack(n_attachments))
            out_file.write(struct_u32.pack(ofs_attachments))

            out_file.write(struct_u32.pack(n_attach_lookup))
            out_file.write(struct_u32.pack(ofs_attach_lookup))

            out_file.write(struct_u32.pack(n_events))
            out_file.write(struct_u32.pack(ofs_events))

            out_file.write(struct_u32.pack(n_lights))
            out_file.write(struct_u32.pack(ofs_lights))

            out_file.write(struct_u32.pack(n_cameras))
            out_file.write(struct_u32.pack(ofs_cameras))

            out_file.write(struct_u32.pack(n_camera_lookup))
            out_file.write(struct_u32.pack(ofs_camera_lookup))

            out_file.write(struct_u32.pack(n_ribbon_emitters))
            out_file.write(struct_u32.pack(ofs_ribbon_emitters))      

            out_file.write(struct_u32.pack(n_particle_emitters))
            out_file.write(struct_u32.pack(ofs_particle_emitters))
            
            # After the header
            
            out_file.write(self.name)
            out_file.write(struct_u8.pack(0)) # string null terminated

            out_file.write(struct_u32.pack(global_seq))

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
            
            out_file.write(struct_i.pack(keybone_id))
            out_file.write(struct_u32.pack(bone_flags))
            out_file.write(struct_h.pack(parent_bone))
            out_file.write(struct_H.pack(bone_unk1))
            out_file.write(struct_H.pack(bone_unk2))
            out_file.write(struct_H.pack(bone_unk3))
            
            out_file.write(struct_h.pack(tr_block[0]))
            out_file.write(struct_h.pack(tr_block[1]))
            out_file.write(struct_u32.pack(tr_block[2]))
            out_file.write(struct_u32.pack(tr_block[3]))
            out_file.write(struct_u32.pack(tr_block[4]))
            out_file.write(struct_u32.pack(tr_block[5]))      
            out_file.write(struct_h.pack(ro_block[0]))
            out_file.write(struct_h.pack(ro_block[1]))
            out_file.write(struct_u32.pack(ro_block[2]))
            out_file.write(struct_u32.pack(ro_block[3]))
            out_file.write(struct_u32.pack(ro_block[4]))
            out_file.write(struct_u32.pack(ro_block[5]))       
            out_file.write(struct_h.pack(sc_block[0]))
            out_file.write(struct_h.pack(sc_block[1]))
            out_file.write(struct_u32.pack(sc_block[2]))
            out_file.write(struct_u32.pack(sc_block[3]))
            out_file.write(struct_u32.pack(sc_block[4]))
            out_file.write(struct_u32.pack(sc_block[5]))     
            out_file.write(struct_f.pack(bone_vector_pivot[0]))
            out_file.write(struct_f.pack(bone_vector_pivot[1]))
            out_file.write(struct_f.pack(bone_vector_pivot[2]))
            
            out_file.write(struct_u32.pack(t1[0]))
            out_file.write(struct_u32.pack(t1[1]))
            out_file.write(struct_u32.pack(t2[0]))
            out_file.write(struct_u32.pack(t2[1]))
            out_file.write(struct_u32.pack(r1[0]))
            out_file.write(struct_u32.pack(r1[1]))
            out_file.write(struct_u32.pack(r2[0]))
            out_file.write(struct_u32.pack(r2[1]))
            out_file.write(struct_u32.pack(s1[0]))
            out_file.write(struct_u32.pack(s1[1]))
            out_file.write(struct_u32.pack(s2[0]))
            out_file.write(struct_u32.pack(s2[1]))

            for i in range (0, len(t1_1)):
                out_file.write(struct_u32.pack(t1_1[i]))     

            for i in range (0, len(t2_1)):
                for j in range (0, len(t2_1[i])):
                    out_file.write(struct_f.pack(t2_1[i][j]))

            for i in range (0, len(r1_1)):
                out_file.write(struct_u32.pack(r1_1[i]))

            for i in range (0, len(r2_1)):
                for j in range (0, len(r2_1[i])):
                    out_file.write(struct_h.pack(r2_1[i][j]))

            for i in range (0, len(s1_1)):
                out_file.write(struct_u32.pack(s1_1[i]))

            for i in range (0, len(s2_1)):
                for j in range (0, len(s2_1[i])):
                    out_file.write(struct_f.pack(s2_1[i][j]))
            
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
            out_file.write(struct_u32.pack(3)) # texture flags : put 3 to wrap_x and wrap_y if you have multiple UV islands
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
        
            """
        
            for i in range (0, len(collisions_triangles)):
                for j in range (0, len(collisions_triangles[i])):
                    out_file.write(struct_h.pack(collisions_triangles[i][j]))

            for i in range (0, len(collisions_vertices)):
                for j in range (0, len(collisions_vertices[i])):
                    out_file.write(struct_f.pack(collisions_vertices[i][j]))

            for i in range (0, len(collisions_normals)):
                for j in range (0, len(collisions_normals[i])):
                    out_file.write(struct_f.pack(collisions_normals[i][j]))

            """

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
                out_skin_file.write(struct_H.pack(i))
            
            for tri in self.triangles:
                out_skin_file.write(struct_H.pack(tri))
            
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

            translation_ts = []
            translation_values = []      
            rotation_ts = []
            rotation_values = []
            scaling_ts = []
            scaling_values = []

            # Initialised to -1 in case there's no input values.
            translation_ts_location = -1
            translation_values_location = -1
            rotation_ts_location = -1
            rotation_values_location = -1
            scaling_ts_location = -1
            scaling_values_location = -1

            if ( gltf.get('animations', []) ):
                channel_number = len(gltf.get('channels', [])) - 1
                for anim in gltf.get('animations', []):
                    for channel in anim['channels']:
                        sampler_number =  anim['channels'][channel_number]['sampler']
                  
                    # if node on the anim == mesh_number, then get sampler number and get all corresponding samplers
                        if gltf.get('nodes', [])[ anim['channels'][0]['target']['node'] ]['mesh'] == mesh_number:
                            if anim['channels'][sampler_number]['target']['path'] == "translation":
                                translation_ts_location = anim['samplers'][sampler_number]['input']
                                translation_values_location =  anim['samplers'][sampler_number]['output']
                                if ( anim['samplers'][sampler_number]['interpolation'] != "LINEAR"): 
                                    print("Translation interpolation is not linear, please fix that and relaunch the conversion. Exiting.")
                                    sys.exit(0)
                            if anim['channels'][sampler_number]['target']['path'] == "rotation":
                                rotation_ts_location = anim['samplers'][sampler_number]['input']
                                rotation_values_location =  anim['samplers'][sampler_number]['output']
                                if ( anim['samplers'][sampler_number]['interpolation'] != "LINEAR"): 
                                    print("Rotations interpolation is not linear, please fix that and relaunch the conversion. Exiting.")
                                    sys.exit(0)
                            if anim['channels'][sampler_number]['target']['path'] == "scale":
                                scaling_ts_location = anim['samplers'][sampler_number]['input']
                                scaling_values_location =  anim['samplers'][sampler_number]['output']
                                if ( anim['samplers'][sampler_number]['interpolation'] != "LINEAR"): 
                                    print("Scaling interpolation is not linear, please fix that and relaunch the conversion. Exiting.")
                                    sys.exit(0)
                            channel_number = channel_number - 1
            
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

                if ( translation_ts_location != -1 ):
                    # Get translation ts of the whole current mesh
                    bin_file.seek(current_mesh_info[translation_ts_location]['byteLength'])
                    grab = bin_file.tell()
                    bin_file.seek(current_mesh_info[translation_ts_location]['byteOffset'])
                    for i in range (0, grab / 4) :
                        translation_ts.append(_get_f(bin_file) * 1000) # TODO : best place to convert s -> ms ?

                    # Get translation values of the whole current mesh
                    bin_file.seek(current_mesh_info[translation_values_location]['byteLength'])
                    grab = bin_file.tell()
                    bin_file.seek(current_mesh_info[translation_values_location]['byteOffset'])
                    for i in range (0, grab / 12) : 
                        translation_values.append([])
                        for j in range (0, 3):
                            translation_values[i].append( _get_f(bin_file) )

                if ( rotation_ts_location != -1 ):
                    # Get rotation ts of the whole current mesh
                    bin_file.seek(current_mesh_info[rotation_ts_location]['byteLength'])
                    grab = bin_file.tell()
                    bin_file.seek(current_mesh_info[rotation_ts_location]['byteOffset'])
                    for i in range (0, grab / 4) :
                        rotation_ts.append(_get_f(bin_file) * 1000) # TODO : best place to convert s -> ms ?

                    # Get rotation values of the whole current mesh
                    bin_file.seek(current_mesh_info[rotation_values_location]['byteLength'])
                    grab = bin_file.tell()
                    bin_file.seek(current_mesh_info[rotation_values_location]['byteOffset'])
                    for i in range (0, grab / 16) : 
                        rotation_values.append([])
                        for j in range (0, 4):
                            current_rot = _get_f(bin_file)
                            if ( str( current_rot ) == "-0.0" ): # ieee 754 and Python don't really care about -0, but we do.
                                rotation_values[i].append( -32768.0 )
                            else:
                                rotation_values[i].append( _quat_float_to_short(current_rot))
            
                    rotation_values[0] = [32767, 32767, 32767, -1]
                    rotation_values[ len(rotation_values) - 1 ] = [-32768, -32768, -32768, 0]

                if ( scaling_ts_location != -1 ):
                    # Get scaling ts of the whole current mesh
                    bin_file.seek(current_mesh_info[scaling_ts_location]['byteLength'])
                    grab = bin_file.tell()
                    bin_file.seek(current_mesh_info[scaling_ts_location]['byteOffset'])
                    for i in range (0, grab / 4) :
                        scaling_ts.append(_get_f(bin_file) * 1000) # TODO : best place to convert s -> ms ?

                    # Get scaling values of the whole current mesh
                    bin_file.seek(current_mesh_info[scaling_values_location]['byteLength'])
                    grab = bin_file.tell()
                    bin_file.seek(current_mesh_info[scaling_values_location]['byteOffset'])
                    for i in range (0, grab / 12) : 
                        scaling_values.append([])
                        for j in range (0, 3):
                            scaling_values[i].append( _get_f(bin_file) )
                            
            models_list.append( Model(mesh['name'], mesh_texture, vertices, normals, triangles, texture_coords_0, mesh_min_bounds, mesh_max_bounds, translation_ts, translation_values, rotation_ts, rotation_values, scaling_ts, scaling_values) )
            mesh_number = mesh_number - 1
    return models_list

""" MAIN STUFF 
"""

# load, write to m2, quit.

scene_gltf_name = "doubletexture.gltf" # default name for testing.
m2_texture_path = "world\\doubletexture\\" # default name for testing.

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
#print(all_models[0].translation_ts)
#print(all_models[0].translation_values)
#print(all_models[0].rotation_ts)
#print(all_models[0].rotation_values)
#print(all_models[0].scaling_ts)
#print(all_models[0].scaling_values)

all_models[0].write_m2(m2_texture_path)
