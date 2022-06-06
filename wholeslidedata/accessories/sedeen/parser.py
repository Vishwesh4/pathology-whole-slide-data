from typing import Dict
import xml.etree.ElementTree as ET

from wholeslidedata.annotation.parser import (
    AnnotationParser,
    AnnotationType,
    InvalidAnnotationParserError,
)
from wholeslidedata.labels import Labels

@AnnotationParser.register(("sedeen",))
class SedeenAnnotationParser(AnnotationParser):

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
            # if given_label is not None:
            #     if labels[i] in given_label.keys():
            #         name = given_label[labels[i]]
            labels_construct.append({"name":name,"value":i+1,"color":labels[i]})
        
        return Labels.create(labels_construct)

    def _get_label(self, child, labels: Labels, type):
        name = self._get_label_name(child, labels, type)
        if name not in labels.names:
            return None

        label = labels.get_label_by_name(name)
        label = label.todict()
        return label

    def _get_label_name(self, child, labels, type) -> str:
        if type in labels.names:
            return type
        return child.attrib.get("color")[1:]

    def _get_annotation_type(self, child):
        annotation_type = child.attrib.get("type").lower()
        if annotation_type in SedeenAnnotationParser.TYPES:
            return SedeenAnnotationParser.TYPES[annotation_type]
        raise ValueError(f"unsupported annotation type in {child}")

    def _get_coords(self, child):
        coords = []
        for coordinates in child:
            nums = coordinates.text.split(",")
            coords.append([float(nums[0]),float(nums[1])])
        return coords
    
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