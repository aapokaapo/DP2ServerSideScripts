import operator
import math
import struct
from PIL import Image, ImageDraw, ImageFont
from statistics import mean


class Q2BSP:
    def __init__(self, map_path):
        with open(map_path, "rb") as f:
            self.__bytes1 = f.read()
            self.magic, self.map_version = self.__get_header()
            self.lump_sizes, self.lump_order = self.__get_lump_sizes()
            self.binary_lumps = self.__get_binary_lumps()
            self.n_clusters, self.clusters = self.__get_vis()
            self.leaf_faces = self.__get_leaf_faces()
            self.faces = self.__get_faces()
            self.n_tex_infos, self.tex_infos = self.__get_tex_info()
            self.n_models, self.models = self.__get_models()
            self.vertices = self.__get_vertices()
            self.edge_list = self.__get_edges()
            self.face_edges = self.__get_face_edges()
            self.__get_vertices_of_faces()
            self.bsp_leaves = self.__get_bsp_leafs()
            for leaf in self.bsp_leaves:
                leaf.get_center(self.faces, self.leaf_faces)
            for model in self.models:
                model.get_center(self.faces)
            self.__get_entities()
            self.nodes = self.__get_bsp_nodes()

    def __get_header(self):
        magic = self.__bytes1[0:4].decode("ascii", "ignore")
        version = int.from_bytes(self.__bytes1[4:8], byteorder='little', signed=False)
        return magic, version

    def __get_lump_sizes(self):
        lump_list = list()
        lump_names = ["Entities",
                      "Planes",
                      "Vertices",
                      "Visibility",
                      "Nodes",
                      "Texture Information",
                      "Faces",
                      "Lightmaps",
                      "Leaves",
                      "Leaf Face Table",
                      "Leaf Brush Table",
                      "Edges",
                      "Face Edge Table",
                      "Models",
                      "Brushes",
                      "Brush Sides",
                      "Pop",
                      "Areas",
                      "Area Portals"]
        for i in range(19):
            lump_list.append({"offset": int.from_bytes(self.__bytes1[8+8*i:12+8*i], byteorder="little", signed=False),
                              "length": int.from_bytes(self.__bytes1[12+8*i:16+8*i], byteorder="little", signed=False)})
            lump_list[i]["lump_end"] = lump_list[i]["offset"]+lump_list[i]["length"]
            lump_list[i]["lump"] = lump_names[i]

        # for getting lump order
        indiced_list = list()
        for i in range(19):
            indiced_list.append([lump_list[i]["offset"], i])
        indiced_list = sorted(indiced_list, key=operator.itemgetter(0))
        return lump_list, [x[1] for x in indiced_list]

    def __get_binary_lumps(self):
        lump_list = list()
        for i in range(19):
            lump_list.append(self.__bytes1[self.lump_sizes[i]["offset"]:self.lump_sizes[i]["lump_end"]])
        return lump_list

    def __get_vertices(self):
        vert_list = list()
        n_verts = int(self.lump_sizes[2]["length"]/12)
        for i in range(n_verts):
            vert_list.append(struct.unpack("<fff",self.binary_lumps[2][12*i:12*(i+1)]))
        return vert_list

    class BSPNode:
        def __init__(self, node_bytes):
            self.plane = int.from_bytes(node_bytes[0:4], byteorder="little", signed=False)
            self.front_child = int.from_bytes(node_bytes[4:8], byteorder="little", signed=True)
            self.back_child = int.from_bytes(node_bytes[8:12], byteorder="little", signed=True)
            self.bbox_min = [None]*3
            self.bbox_max = [None]*3
            self.bbox_min = struct.unpack("<hhh", node_bytes[12:18])
            self.bbox_max = struct.unpack("<hhh", node_bytes[18:24])
            self.first_face = int.from_bytes(node_bytes[24:26], byteorder="little")
            self.num_faces = int.from_bytes(node_bytes[26:28], byteorder="little")

    def __get_bsp_nodes(self):
        n_nodes = int(self.lump_sizes[4]["length"]/28)
        node_list = list()
        for i in range(n_nodes):
            node_list.append(self.BSPNode(self.binary_lumps[4][28*i:28*(i+1)]))
        return node_list

    class Cluster:
        def __init__(self, compressed_pvs, compressed_phs, n_clusters):
            self.compressed_pvs = compressed_pvs
            self.compressed_phs = compressed_phs
            self.n_clusters = n_clusters

        def __decompress_bytes(self, compressed_bytes):
            decompressed = list()
            i=0
            while i < len(compressed_bytes):
                value = int.from_bytes(compressed_bytes[i:i+1 if i+1<len(compressed_bytes) else None], byteorder="little", signed=False)
                if value == 0:
                    decompressed.extend([0]*int.from_bytes(compressed_bytes[i+1:i+2 if i+2<len(compressed_bytes) else None], byteorder="little", signed=False))
                    i+=1
                else:
                    decompressed.append(value)
                i+=1
            return decompressed

        def runtime_compress(self, zero_count):
            compressed = b""
            while zero_count > 255:
                compressed+=bytes(1)
                compressed+=(255).to_bytes(1, byteorder="little")
                zero_count-=255
            if zero_count > 0:
                compressed+=bytes(1)
                compressed+=zero_count.to_bytes(1, byteorder="little")
            return compressed

        def __compress_bytes(self, decompressed_bytes):
            # print(f"to compress: {decompressed_bytes}")
            compressed = b""
            counter=0
            for i in range(len(decompressed_bytes)):
                current_byte = int.from_bytes(decompressed_bytes[i:i+1 if i+1 < len(decompressed_bytes) else None], byteorder="little")
                if current_byte == 0:
                    counter+=1
                else:
                    if not counter == 0:
                        compressed += self.runtime_compress(counter)
                        counter = 0
                    compressed += bytes([current_byte])
            if not counter==0:
                compressed += self.runtime_compress(counter)
            # print(f"compressed: {[x for x in compressed]}")
            return compressed

        def get_pvs(self):
            # print([int.from_bytes([x], byteorder="little") for x in self.compressed_pvs])
            # print(f"-len decompressed: {len(self.__decompress_bytes(self.compressed_pvs))} decompressed pvs: {self.__decompress_bytes(self.compressed_pvs)}")
            return self.__decompress_bytes(self.compressed_pvs)

        def get_phs(self):
            return self.__decompress_bytes(self.compressed_phs)

        def set_pvs(self, pvs):
            self.compressed_pvs = self.__compress_bytes(pvs)

        def set_phs(self, phs):
            self.compressed_phs = self.__compress_bytes(phs)

        def set_visible(self, byte_list, index):
            value_list = self.get_pvs()
            if byte_list == "phs":
                value_list = self.get_phs()
            # print(f"index: {index} - value list {value_list}")
            byte_index = int(index/8)
            bit_index = index % 8
            """Set the index:th bit of v to 1 if x is truthy, else to 0, and return the new value."""
            mask = 1 << bit_index  # Compute mask, an integer with just bit 'index' set.
            value_list[byte_index] |= mask  # If x was True, set the bit indicated by the mask.
            print(f"byte index: {byte_index} - result: {value_list} - length value_list: {len(value_list)} - num_clusters: {self.n_clusters} ")
            if byte_list=="phs":
                self.compressed_phs==self.__compress_bytes(value_list)
            else:
                self.compressed_pvs == self.__compress_bytes(value_list)
            return value_list  # Return the result, we're done.

        def set_invisible(self, byte_list, index):
            value_list = self.get_pvs()
            if byte_list == "phs":
                value_list = self.get_phs()
            byte_index = int(index/8)
            bit_index = index % 8
            """Set the index:th bit of v to 1 if x is truthy, else to 0, and return the new value."""
            mask = 1 << bit_index  # Compute mask, an integer with just bit 'index' set.
            value_list[byte_index] &= ~mask  # Clear the bit indicated by the mask (if x is False)
            if byte_list=="phs":
                self.compressed_phs==self.__compress_bytes(value_list)
            else:
                self.compressed_pvs == self.__compress_bytes(value_list)

            return value_list  # Return the result, we're done.

    def __get_vis(self):
        n_clusters = int.from_bytes(self.binary_lumps[3][:4], byteorder='little', signed=False)
        # print(n_clusters)
        pvs_offsets = list()
        phs_offsets = list()
        for i in range(n_clusters):
            pvs_offset = int.from_bytes(self.binary_lumps[3][4+8*i:4+8*i+4], byteorder='little', signed=False)
            pvs_offsets.append(pvs_offset)
            # print(pvs_offset)
            phs_offset = int.from_bytes(self.binary_lumps[3][4+8*i+4:4+8*i+8], byteorder='little', signed=False)
            phs_offsets.append(phs_offset)
            # print(phs_offset)

        clusters = list()
        for i in range(n_clusters):
            clusters.append(self.Cluster(self.binary_lumps[3][pvs_offsets[i]:pvs_offsets[i+1] if i+1 < len(pvs_offsets) else phs_offsets[0]],
                                         self.binary_lumps[3][phs_offsets[i]:phs_offsets[i+1] if i+1 < len(phs_offsets) else self.lump_sizes[3]["length"]], n_clusters))
        return n_clusters, clusters

    def save_vis(self, clusters):
        old_vis = self.binary_lumps[3]
        vis_bytes = b""
        # print(self.n_clusters)
        # print(f"--{len(clusters)}")
        vis_bytes += len(clusters).to_bytes(4, byteorder="little")
        pvs_offsets_counter = 4 + 8*len(clusters)
        pvs_offsets = list()
        phs_offsets_counter = 4 + 8*len(clusters)
        for i in range(len(clusters)):
            phs_offsets_counter+=len(self.clusters[i].compressed_pvs)
        initial_phs_offset = phs_offsets_counter
        phs_offsets = list()
        for i in range(len(clusters)):
            pvs_offsets.append(pvs_offsets_counter)
            pvs_offsets_counter += len(self.clusters[i].compressed_pvs)
            phs_offsets.append(phs_offsets_counter)
            phs_offsets_counter += len(self.clusters[i].compressed_phs)
        for i in range(len(clusters)):
            vis_bytes += pvs_offsets[i].to_bytes(4, byteorder="little")
            vis_bytes += phs_offsets[i].to_bytes(4, byteorder="little")
        for i in range(len(clusters)):
            # print(f"offset: {pvs_offsets[i]} - current: {len(vis_bytes)}")
            vis_bytes += self.clusters[i].compressed_pvs
        for i in range(len(clusters)):
            vis_bytes += self.clusters[i].compressed_phs
        print(f"initial phs: {initial_phs_offset} - last pvs: {pvs_offsets_counter}")

        self.binary_lumps[3] = vis_bytes

    class TexInfo:
        def __init__(self, tex_info_bytes):
            self.u_axis = struct.unpack('<fff', tex_info_bytes[0:12])
            [self.u_offset] = struct.unpack('<f', tex_info_bytes[12:16])
            self.v_axis = struct.unpack('<fff', tex_info_bytes[16:28])
            [self.v_offset] = struct.unpack('<f', tex_info_bytes[28:32])
            self.flags = int.from_bytes(tex_info_bytes[32:36], byteorder="little", signed=False)
            self.flags = 0
            self.contents = 1
            self.value = int.from_bytes(tex_info_bytes[36:40], byteorder="little", signed=False)
            self.__texture_name = tex_info_bytes[40:72]
            self.next_texinfo = int.from_bytes(tex_info_bytes[72:76], byteorder="little", signed=False)

        def tex_to_bytes(self):
            tex_bytes = b""
            for x in self.u_axis:
                tex_bytes+=bytearray(struct.pack("<f", x))
                # tex_bytes+=x.to_bytes(4, byteorder="little")
            # tex_bytes+= self.u_offset.to_bytes(4, byteorder="little")
            tex_bytes+= bytearray(struct.pack("<f", self.u_offset))
            for x in self.v_axis:
                tex_bytes+=bytearray(struct.pack("<f", x))
                # tex_bytes+=x.to_bytes(4, byteorder="little")
            tex_bytes+= bytearray(struct.pack("<f", self.v_offset))
            # tex_bytes+= self.v_offset.to_bytes(4, byteorder="little")
            tex_bytes+=self.flags.to_bytes(4, byteorder="little")
            tex_bytes+=self.value.to_bytes(4, byteorder="little")
            tex_bytes+=self.__texture_name
            tex_bytes+=self.next_texinfo.to_bytes(4, byteorder="little")
            return tex_bytes


        def get_texture_name(self):
            return self.__texture_name.decode("ascii", "ignore").replace("\x00", "")

        def set_texture_name(self, name):
            full_name = str.encode(name)+bytes(32-len(name))
            self.__texture_name = full_name

    def __get_tex_info(self):
        n_tex_info = int(self.lump_sizes[5]["length"]/76)
        tex_info_list = list()
        for i in range(n_tex_info):
            tex_info_list.append(self.TexInfo(self.binary_lumps[5][76*i:76*(i+1)]))
        return n_tex_info, tex_info_list

    def save_tex_info(self, tex_info_list):
        new_tex_info=b""
        for i in range(len(tex_info_list)):
            new_tex_info += tex_info_list[i].tex_to_bytes()
        self.binary_lumps[5] = new_tex_info

    class Face:
        def __init__(self, face_bytes):
            self.original_bytes = face_bytes
            self.first_edge = int.from_bytes(face_bytes[4:8], byteorder="little", signed=False)
            self.num_edges = int.from_bytes(face_bytes[8:10], byteorder="little", signed=False)
            self.texture_info = int.from_bytes(face_bytes[10:12], byteorder="little", signed=False)
            self.lightmap_styles = int.from_bytes(face_bytes[12:16], byteorder="little", signed=False)
            self.lightmap_offsets = int.from_bytes(face_bytes[16:20], byteorder="little", signed=False)
            self.vertices = list()

        def save_to_bytes(self):
            new_bytes = b""
            new_bytes+=self.original_bytes[:4]
            new_bytes+=self.first_edge.to_bytes(4, byteorder="little")
            new_bytes+=self.num_edges.to_bytes(2, byteorder="little")
            new_bytes+=self.texture_info.to_bytes(2, byteorder="little")
            new_bytes+=self.lightmap_styles.to_bytes(4, byteorder="little")
            new_bytes+=self.lightmap_offsets.to_bytes(4, byteorder="little")
            return new_bytes

    def __get_faces(self):
        num_faces = int(self.lump_sizes[6]["length"]/20)
        face_list = list()
        for i in range(num_faces):
            face_list.append(self.Face(self.binary_lumps[6][20*i:20*(i+1)]))
        return face_list

    def save_faces(self, faces):
        new_bytes = b""
        for face in faces:
            new_bytes += face.save_to_bytes()
        self.binary_lumps[6] = new_bytes

    class BSPLeaf:
        def __init__(self, leaf_bytes):
            self.cluster = int.from_bytes(leaf_bytes[4:6], byteorder="little", signed=False)
            self.first_leaf_face = int.from_bytes(leaf_bytes[20:22], byteorder="little")
            self.num_leaf_faces = int.from_bytes(leaf_bytes[22:24], byteorder="little")
            print(f"num leaf faces: {self.num_leaf_faces}")
            self.__bytes_list = leaf_bytes
            self.center = list()
            self.bbox_min = [None]*3
            self.bbox_max = [None]*3
            (self.bbox_min[:]) = struct.unpack("<hhh", leaf_bytes[8:14])
            (self.bbox_max[:]) = struct.unpack("<hhh", leaf_bytes[14:20])

        def get_center(self, faces, leaf_faces):
            own_faces = list()
            print(f"num faces: {self.num_leaf_faces}")
            for i in range(self.num_leaf_faces):
                own_faces.append(faces[leaf_faces[self.first_leaf_face+i]].vertices)
            print(f"own_faces: {own_faces}")
            own_faces = [c for b in own_faces for c in b]
            own_faces = [c for b in own_faces for c in b]
            own_faces = [[int(c) for c in b] for b in own_faces]
            print(f"own_faces: {own_faces}")
            if own_faces:
                # print(f"local: {[x[0][0] for x in own_faces]}")

                self.center = [mean([x[0] for x in own_faces]),mean([x[1] for x in own_faces]), mean([x[2] for x in own_faces])]
            # print(f"center: {self.center}")

        def save_to_bytes(self):
            before_faces = b""+self.__bytes_list[:4]+self.cluster.to_bytes(2, byteorder="little")+self.__bytes_list[6:8]
            for i in range(3):
                before_faces += struct.pack("<h", self.bbox_min[i])
            for i in range(3):
                before_faces += struct.pack("<h", self.bbox_max[i])
            faces = b""+self.first_leaf_face.to_bytes(2, byteorder="little")+self.num_leaf_faces.to_bytes(2, byteorder="little")
            # print(f"faces: {faces} - old faces: {self.__bytes_list[20:24]}")
            self.__bytes_list =before_faces+faces+self.__bytes_list[24:28]
            return self.__bytes_list

    def __get_bsp_leafs(self):
        n_bsp_leafs = int(self.lump_sizes[8]["length"]/28)
        bsp_leaf_list = list()
        for i in range(n_bsp_leafs):
            bsp_leaf_list.append(self.BSPLeaf(self.binary_lumps[8][28*i:28*(i+1)]))
        return bsp_leaf_list

    def save_bsp_leaves(self, bsp_leaves):
        new_lump=b""
        for i in range(len(bsp_leaves)):
            new_lump+=bsp_leaves[i].save_to_bytes()
        self.binary_lumps[8]=new_lump

    def __get_leaf_faces(self):
        n_leaf_faces = int(self.lump_sizes[9]["length"]/2)
        leaf_face_list = list()
        for i in range((n_leaf_faces)):
            leaf_face_list.append(int.from_bytes(self.binary_lumps[9][2*i:2*i+2], byteorder="little"))
        return leaf_face_list

    def save_leaf_faces(self, leaf_face_bytes):
        print(f"len: {len(leaf_face_bytes)} > before leaf faces: \n{leaf_face_bytes} \nlen: {len(self.leaf_faces)} (maybe) after: \n {self.leaf_faces} \n equal: {leaf_face_bytes == self.leaf_faces}")
        new_bytes = b""
        for i in leaf_face_bytes:
            new_bytes+=i.to_bytes(2, byteorder="little")
        self.binary_lumps[9]=new_bytes

    def __get_edges(self):
        edge_list = list()
        n_edges = int(self.lump_sizes[11]["length"]/4)
        for i in range(n_edges):
            edge_list.append(struct.unpack("<HH", self.binary_lumps[11][4*i:4*(i+1)]))
        return edge_list

    def __get_face_edges(self):
        face_edge_list = list()
        n_face_edges = int(self.lump_sizes[12]["length"]/4)
        for i in range(n_face_edges):
            face_edge_list.append(abs(int.from_bytes(self.binary_lumps[12][4*i:4*(i+1)], byteorder="little", signed=True)))
        return face_edge_list

    def __get_entities(self):
        entity_bytes = self.binary_lumps[0].decode("ascii")
        print(entity_bytes)

    class Model:
        def __init__(self, model_bytes):
            self.__model_bytes = model_bytes
            self.bbox_min = [None]*3
            self.bbox_max = [None]*3
            self.origin = [None]*3
            (self.bbox_min[:]) = struct.unpack("<fff", model_bytes[0:12])
            (self.bbox_max[:]) = struct.unpack("<fff", model_bytes[12:24])
            (self.origin[:]) = struct.unpack("<fff", model_bytes[24:36])
            self.first_face = int.from_bytes(model_bytes[40:44], byteorder="little")
            self.num_faces = int.from_bytes(model_bytes[44:48], byteorder="little")
            self.center = list()

        def get_center(self, faces):
            own_faces = list()
            for i in range(self.num_faces):
                own_faces.append(faces[self.first_face+i].vertices)
            print(f"own_faces: {own_faces}")
            own_faces = [c for b in own_faces for c in b]
            own_faces = [c for b in own_faces for c in b]
            own_faces = [[int(c) for c in b] for b in own_faces]
            if own_faces:
                # print(f"local: {[x[0][0] for x in own_faces]}")
                self.center = [mean([x[0] for x in own_faces]),mean([x[1] for x in own_faces]), mean([x[2] for x in own_faces])]

        def save_to_bytes(self):
            before_bytes = b""
            for i in range(3):
                before_bytes += struct.pack("<f", self.bbox_min[i])
            for i in range(3):
                before_bytes += struct.pack("<f", self.bbox_max[i])
            for i in range(3):
                before_bytes += struct.pack("<f", self.origin[i])

            new_bytes = before_bytes + self.__model_bytes[36:40]+self.first_face.to_bytes(4, byteorder="little")+ self.num_faces.to_bytes(4, byteorder="little")
            self.__model_bytes=new_bytes
            return new_bytes

    def __get_models(self):
        n_models = int(self.lump_sizes[13]["length"]/48)
        model_list = list()
        for i in range(n_models):
            model_list.append(self.Model(self.binary_lumps[13][48*i:48*(i+1)]))
        return n_models, model_list

    def save_models(self, models):
        new_bytes = b""
        for i in range(len(models)):
            new_bytes += models[i].save_to_bytes()
        self.binary_lumps[13]=new_bytes

    def save_brushes_temp(self, brush_bytes):
        num_bytes = int(len(brush_bytes)/12)
        print(f"size: {len(brush_bytes)} - divided: {len(brush_bytes)/12}")
        new_bytes = b""
        for i in range(num_bytes):
            new_bytes+=brush_bytes[12*i:12*i+8]
            new_bytes+=(1).to_bytes(4, byteorder="little", signed=False)
        print(f"new: {len(new_bytes)}")
        self.binary_lumps[14]=new_bytes

    def __get_vertices_of_faces(self):
        # print(f"len vertices: {len(self.vertices)} - max: {max(self.edge_list)}")
        # print(f"verts: {self.vertices}\n - min: {min(self.vertices)} - max: {max(self.vertices)} - len: {len(self.vertices)}")
        # print(f"edges: {self.edge_list}\n - min: {min(self.edge_list)} - max: {max(self.edge_list)} - len: {len(self.edge_list)}")
        # print(f"face edges: {self.face_edges}\n - min: {min(self.face_edges)} - max: {max(self.face_edges)} - len: {len(self.face_edges)}")
        # print(f"faces: {self.faces}\n - min: {min([x.num_edges+x.first_edge for x in self.faces])} - max: {max([x.num_edges+x.first_edge for x in self.faces])} - len: {len([x.num_edges+x.first_edge for x in self.faces])}")
        for idx, face in enumerate(self.faces):
            # print()
            face_edges = self.face_edges[face.first_edge:face.first_edge+face.num_edges]
            # print(f"face edges: {face_edges} len: {len(self.edge_list)}")
            # print(f"max edge: {max([self.edge_list[x] for x in face_edges])} len: {len(self.edge_list)} - max: {max(self.edge_list)}")
            # print([self.edge_list[self.face_edges[x]] for x in face_edges])
            # print([(self.vertices[self.edge_list[self.face_edges[x]][0]],self.vertices[self.edge_list[self.face_edges[x]][1]]) for x in face_edges])
            # edges = list()
            # for face_edge in face_edges:
            #     edges.append(self.face_edges[face_edge])
            # verts = list()
            # for edge in edges:
            #     # print(f"edge: {edge} - len vertices: {len(self.vertices)}")
            #     verts.append(self.vertices[edge])
            self.faces[idx].vertices = [(self.vertices[self.edge_list[self.face_edges[x]][0]],self.vertices[self.edge_list[self.face_edges[x]][1]]) for x in face_edges]

    def insert_leaf_faces(self, face_list, index):
        """
        inserts faces at given index
        :param face_list:
        :param index:
        :return:
        """
        print(f"old len of leaf face table: {len(self.leaf_faces)}")
        print(f"increase num_leaf_faces at pos: {index} - {[(x.first_leaf_face, x.num_leaf_faces) for x in self.bsp_leaves if x.first_leaf_face < index and x.num_leaf_faces + x.first_leaf_face >= index]} by {len(face_list)}")
        print(f"increase first_leaf_face: {index} - {[(x.first_leaf_face, x.num_leaf_faces) for x in self.bsp_leaves if x.first_leaf_face >= index]}")
        for face in face_list:
            print(f"inserted face: {face}")
            self.leaf_faces.insert(index, face)
        print(f"new len of leaf face table: {len(self.leaf_faces)}")
        for idx, leaf in enumerate(self.bsp_leaves):
            if leaf.first_leaf_face < index <= leaf.num_leaf_faces + leaf.first_leaf_face:
                self.bsp_leaves[idx].num_leaf_faces += len(face_list)
                print(f"increased num faces of bsp leaf {idx} to {self.bsp_leaves[idx].num_leaf_faces}")
            elif leaf.first_leaf_face >= index:
                self.bsp_leaves[idx].first_leaf_face+=len(face_list)

    def update_lump_sizes(self):
        self.save_vis(self.clusters)
        self.save_tex_info(self.tex_infos)
        self.save_bsp_leaves(self.bsp_leaves)
        self.save_models(self.models)
        self.save_leaf_faces(self.leaf_faces)
        self.save_brushes_temp(self.binary_lumps[14])
        self.save_faces(self.faces)
        current_offset = 160  # 20*8+8
        for i in range(19):
            self.lump_sizes[self.lump_order[i]]["length"] = len(self.binary_lumps[self.lump_order[i]])
            self.lump_sizes[self.lump_order[i]]["offset"] = current_offset
            self.lump_sizes[self.lump_order[i]]["lump_end"] = current_offset + len(self.binary_lumps[self.lump_order[i]])
            current_offset +=((len(self.binary_lumps[self.lump_order[i]])+3)&~3)

    def save_map(self, path, prefix):
        bytes2 = str.encode(self.magic)
        bytes2 += self.map_version.to_bytes(4, byteorder="little")
        for i in range(19):
            bytes2 += self.lump_sizes[i]["offset"].to_bytes(4, byteorder='little')
            bytes2 += self.lump_sizes[i]["length"].to_bytes(4, byteorder='little')
        for i in range(19):
            bytes2 += self.binary_lumps[self.lump_order[i]] + bytes(
                ((len(self.binary_lumps[self.lump_order[i]]) + 3) & ~3) - len(
                    self.binary_lumps[self.lump_order[i]]))
        with open(path.replace(".bsp", prefix+".bsp"), "w+b") as h:
            h.write(bytes2)


def numbered_texture(path, text):
    font = ImageFont.truetype("arial.ttf", 25)
    img = Image.new('RGB', font.getsize(text), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((0, 0), text, fill=(255, 0, 0), font=font)
    img.save(path)
