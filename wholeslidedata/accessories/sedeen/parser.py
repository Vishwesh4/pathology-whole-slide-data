from typing import Dict, List
import xml.etree.ElementTree as ET
import numpy as np

from wholeslidedata.annotation.parser import (
    AnnotationParser,
    AnnotationType,
    InvalidAnnotationParserError,
)
from wholeslidedata.labels import Labels
from wholeslidedata.annotation.structures import Annotation

@AnnotationParser.register(("sedeen",))
class SedeenAnnotationParser(AnnotationParser):

    ANNULAR_LABEL = "00ff00ff"
    HOLLOW_LABEL = {"name":"Rest","value":0}
    TYPES = {
        "polygon": AnnotationType.POLYGON,
        "rectangle": AnnotationType.POLYGON,
        "dot": AnnotationType.POINT,
        "spline": AnnotationType.POLYGON,
        "pointset": AnnotationType.POINT,
        "ellipse": AnnotationType.POLYGON,
        "polyline": AnnotationType.POLYGON
    }

    @staticmethod
    def get_available_labels(open_annotations):
        labels = []
        for child in open_annotations:
            if (child.tag == "graphic") & (child.attrib.get("type")!="text"):
                for grandchild in child:
                    if grandchild.tag == "pen":
                        labels.append(grandchild.attrib.get("color"))
        #Construct using Labels
        labels_construct = []
        labels = list(set(labels))
        for i in range(len(labels)):
            name = labels[i][1:]
            labels_construct.append({"name":name,"value":i+1,"color":labels[i]})
        
        return Labels.create(labels_construct)

    def _get_label(self, child, labels: Labels, type):
        name = self._get_label_name(child, labels, type)
        if name not in labels.names:
            return None

        label = labels.get_label_by_name(name)
        label = label.todict()
        return label

    @staticmethod
    def _get_label_name(child, labels, type) -> str:
        if type in labels.names:
            return type
        return child.attrib.get("color")[1:]

    @staticmethod
    def _get_annotation_type(child):
        annotation_type = child.attrib.get("type").lower()
        if annotation_type in SedeenAnnotationParser.TYPES:
            return SedeenAnnotationParser.TYPES[annotation_type]
        raise ValueError(f"unsupported annotation type in {child}")

    @staticmethod
    def _get_coords(child):
        coords = []
        for coordinates in child:
            nums = coordinates.text.split(",")
            coords.append([float(nums[0]),float(nums[1])])
        return coords

    @staticmethod
    def _create_new_annotation(index,type,coords,label,holes=[]):
        annotation = {"index":index,
                      "type":type,
                      "coordinates":coords,
                      "label":label}
        if len(holes)!=0:
            annotation["holes"] = holes
        return Annotation.create(**annotation)       
    
    def _modify_annotations(self,annotations,annular_index):
        # annular_annotations = [annotations[idx] for idx in annular_index]
        annular_annotations = []
        area_annotation = np.array([annotations[idx].area for idx in annular_index])
        index = list(np.array(annular_index)[np.argsort(area_annotation)[::-1]])
        index_stack = index.copy()

        while len(index_stack)!=0:
            idx_i = index_stack.pop(0)
            for j,idx_j in enumerate(index_stack):
                
                if annotations[idx_i].contains(annotations[idx_j]):
                    index_stack.pop(j)
                    # modify the annotations
                    annotations[idx_i] = self._create_new_annotation(index = idx_i,
                                                                    type = annotations[idx_i].type,
                                                                    coords = annotations[idx_i].coordinates,
                                                                    label = annotations[idx_i].label,
                                                                    holes = [annotations[idx_j].coordinates])

                    annotations[idx_j] = self._create_new_annotation(index = idx_j,
                                                                    type = annotations[idx_j].type,
                                                                    coords = annotations[idx_j].coordinates,
                                                                    label = SedeenAnnotationParser.HOLLOW_LABEL)
                    break  

        return annotations            


    def _parse(self, path):
        tree = ET.parse(path)
        annot = tree.getroot()
        for parent in annot:
            for child in parent:
                if child.tag=="overlays":
                    open_annot = child
                    break

        labels = self._get_labels(open_annot)

        for child in open_annot:
            if (child.tag == "graphic") & (child.attrib.get("type")!="text"):
                type = self._get_annotation_type(child)
                for grandchild in child:
                    if grandchild.tag == "pen":
                        label = self._get_label(grandchild,labels,type)
                    elif grandchild.tag == "point-list":
                        coordinates = self._get_coords(grandchild)
                        if len(coordinates)>0:
                            yield {
                                    "type": type.value,
                                    "coordinates": coordinates,
                                    "label": label,
                                }

    def parse(self, path) -> List[Annotation]:

        if not self._path_exists(path):
            raise FileNotFoundError(path)

        annotations = []
        annular_index = []
        index = 0
        for annotation in self._parse(path):
            annotation["index"] = index
            annotation["coordinates"] = (
                np.array(annotation["coordinates"]) * self._scaling
            )
            #note the index of the potentially annular annotations, in particular green        
            label_name = annotation["label"]
            annotation["label"] = self._rename_label(annotation["label"])
            temp_annotation = Annotation.create(**annotation)
            #necessary step due to number of repeated annotations
            if temp_annotation not in annotations:
                annotations.append(temp_annotation)
                if label_name["name"] == SedeenAnnotationParser.ANNULAR_LABEL:
                    annular_index.append(index)
                index+=1

        #Add holes in annular annotations
        annotations = self._modify_annotations(annotations,annular_index)

        return annotations