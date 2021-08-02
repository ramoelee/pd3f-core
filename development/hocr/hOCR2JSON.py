#!/usr/bin/env python
# coding: utf-8

# In[47]:


from __future__ import unicode_literals

from io import TextIOBase

try:
    TextIOBase = file
except NameError:
    pass  # Forward compatibility with Py3k
from bs4 import BeautifulSoup
import re

#from hocrgeo.models import HOCRDocument

import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)


class HOCRParser:
    """
    Parse hOCR documents

    Takes either a file-like object or a filename
    """

    def __init__(self, fs=None, rawdata=None):
        """
        Initializes a HOCRParser

        :param input: Optional file-like object to read or hOCR as a string.

        """
        self._rawdata = None
        self._bboxreg = re.compile(r"bbox (?P<x0>\d+) (?P<y0>\d+) (?P<x1>\d+) (?P<y1>\d+)")
        self._confreg = re.compile(r"x_wconf (\d+)") #added compilation attributes for x_conf
        self._imagereg = re.compile(r"image (\'|\")(.*)\1")
        self._pagenoreg = re.compile(r"ppageno (\d+)")
        self._doc = None
        self._parseddata = None

        if rawdata:
            self._rawdata = rawdata

        if fs:
            self._rawdata = self._get_data_string(fs)

    def _get_data_string(self, fs):
        if isinstance(fs, TextIOBase):
            return fs.read()
        else:
            try:
                if isinstance(fs, unicode):
                    return fs
                else:
                    clean_fs = unicode(fs, encoding="utf-8")
                    if isinstance(clean_fs, unicode):
                        return clean_fs
            except NameError:
                if isinstance(fs, str):
                    return fs
        raise TypeError("Input is not a readable string or file object")

    def load(self, fsfile):
        """Load a file from a filepath or a file-like instance"""
        fp = None
        if isinstance(fsfile, str):
            try:
                fp = open(fsfile, "rb")
            except IOError as e:
                raise e
        elif isinstance(fs, TextIOBase):
            fp = fsfile
        else:
            raise TypeError("argument must be a file object or a valid filepath")
        self._rawdata = self._get_data_string(fp)

    def loads(self, fs):
        if isinstance(fs, str):
            self._rawdata = self._get_data_string(fs)
        else:
            raise TypeError("argument must be a string or unicode instance")

    @property
    def document(self):
        """Parsed HOCR document"""
        return self._doc

    def parse(self):
        """Parse hOCR document into a python object."""

        def _extract_objects_from_element(root, el_name, el_class):
            nodes = root.find_all(el_name, el_class)
            objects = []
            for n in nodes:
                obj = _extract_features(n)
                objects.append(obj)
            return (nodes, objects)

        def _extract_bbox(fs_str):
            """Regular expression matching on a fs_str that should contain hOCR bbox coordinates."""
            match = self._bboxreg.search(fs_str)
            if match:
                match_tup = match.groups()
                match_list = []
                for value in match_tup:
                    match_list.append(int(value))
                return tuple(match_list)
            return None

        # added features for xconf ####################################################################################
        def _extract_conf(fs_str):
            """Regular expression matching on a fs_str that should contain hOCR x-conf."""
            match = self._confreg.search(fs_str)
            if match:
                match_tup = match.groups()
                match_list = []
                for value in match_tup:
                    match_list.append(int(value))
                return tuple(match_list)
            return None
        ################################################################################################################

        def _extract_features(element):
            """Extract basic hOCR features from a given element."""
            features = {}
            features["id"] = element.get("id")
            title_el = element.get("title", "")
            image_match = self._imagereg.search(title_el)
            if image_match:
                features["image"] = image_match.group(2)
            pageno_match = self._pagenoreg.search(title_el)
            if pageno_match:
                features["pageno"] = int(pageno_match.group(1))
            features["bbox"] = _extract_bbox(title_el)
            features["xconf"] = _extract_conf(title_el) #for the added features
            return features

        if not self._rawdata:
            raise Exception(
                "No fsfile specified. You must specify an fs file when instantiating or as an argument to the parse method"
            )
        soup = BeautifulSoup(self._rawdata, "lxml")

        self._parseddata = {}

        # Extract ocr system metadata
        ocr_system = soup.find("meta", attrs={"name": "ocr-system"})
        self._parseddata["system"] = ocr_system.get("content", None) if ocr_system else None

        # Extract capabilities
        ocr_capabilities = soup.find("meta", attrs={"name": "ocr-capabilities"})
        self._parseddata["capabilities"] = ocr_capabilities.get("content", " ").split(" ") if ocr_capabilities else None

        page_nodes, page_objects = _extract_objects_from_element(soup, "div", "ocr_page")
        page_tup = list(zip(page_nodes, page_objects))
        logger.info("Found {0} page(s)".format(len(page_tup)))

        for page_node, page_obj in page_tup:
            carea_nodes, carea_objects = _extract_objects_from_element(page_node, "div", "ocr_carea")
            careas_tup = list(zip(carea_nodes, carea_objects))

            for c_node, c_obj in careas_tup:
                para_nodes, para_objects = _extract_objects_from_element(c_node, "p", "ocr_par")
                paras_tup = list(zip(para_nodes, para_objects))

                for para_node, para_obj in paras_tup:
                    line_nodes, line_objects = _extract_objects_from_element(para_node, "span", "ocr_line")
                    header_nodes, header_objects = _extract_objects_from_element(para_node, "span", "ocr_header")

                    header_tup = list(zip(header_nodes, header_objects))
                    lines_tup = list(zip(line_nodes, line_objects))

                    if len(lines_tup) != 0:
                        for l_node, l_obj in lines_tup:
                            word_nodes, word_objects = _extract_objects_from_element(l_node, "span", "ocrx_word")
                            words_tup = list(zip(word_nodes, word_objects))

                            for w_node, w_obj in words_tup:
                                word_str = w_node.get_text(strip=True)
                                if word_str:
                                    # logger.info(word_str)
                                     word_obj = w_node.get_text()
                                     w_obj['text'] = word_obj.replace('\n', '').replace('\r', '')
                            l_obj["words"] = word_objects

                        para_obj["lines"] = line_objects
                    elif len(header_tup) != 0:
                        for l_node, l_obj in header_tup:
                            word_nodes, word_objects = _extract_objects_from_element(l_node, "span", "ocrx_word")
                            words_tup = list(zip(word_nodes, word_objects))

                            for w_node, w_obj in words_tup:
                                word_str = w_node.get_text(strip=True)
                                if word_str:
                                    # logger.info(word_str)
                                     word_obj = w_node.get_text()
                                     w_obj['text'] = word_obj.replace('\n', '').replace('\r', '')
                            l_obj["words"] = word_objects

                        para_obj["headers"] = header_objects

                c_obj["paragraphs"] = para_objects

            page_obj["careas"] = carea_objects

        self._parseddata["pages"] = page_objects

        #self._doc = HOCRDocument(self._parseddata)


# In[48]:


import math
def angle(a, b):
    angle = math.atan2(b, a) * 180 / math.pi
    return angle


# In[49]:


def jsonbox_form(boxel, dim, data):
    for m in range(2):
        boxel[dim[m]] = data[m]
    boxel[dim[2]] = data[2] - data[0]
    boxel[dim[3]] = data[3] - data[1]


# In[50]:


def line_extract(ContEl, dim, lineinfo, line_id, kind):
    ContEl['id'] = line_id

    ContEl['type'] = kind

    ContEl['box'] = {}
    jsonbox_form(ContEl['box'], dim, lineinfo['bbox'])

    ContEl['properties'] = {}
    contel = ContEl['properties']
    contel['order'] = line_id


# In[51]:


def font_keep(coordinates, glossary, font_t):
    Spec_Font = {}
    size = round(coordinates['h'] * 1.6, 1)
    if size in font_t:
        font_type = glossary[font_t.index(size)]['id']

    else:
        font_t.append(size)
        Spec_Font['id'] = 'font_' + str(font_t.index(size))
        Spec_Font['size'] = size
        Spec_Font['sizeUnit'] = 'px'
        Spec_Font['color'] = '#000000'
        glossary.append(Spec_Font)
        font_type = Spec_Font['id']

    return font_type


# In[52]:


def word_extract(Contline, dim, Wordinfo, Font_Glossary, font_t, word_id):
    Contline['id'] = word_id

    Contline['type'] = 'word'

    Contline['box'] = {}
    jsonbox_form(Contline['box'], dim, Wordinfo['bbox'])
    coordbox = Contline['box']

    Contline['font'] = font_keep(coordbox, Font_Glossary, font_t)

    Contline['fontSize'] = round(coordbox['h'] * 1.6, 1)

    Contline['conf'] = Wordinfo['xconf'][0]

    Contline['properties'] = {}
    lineel = Contline['properties']
    lineel['order'] = word_id

    if 'text' in Wordinfo.keys():
        Contline['content'] = Wordinfo['text']
    else:
        Contline['content'] = []


# In[53]:


def JsonFormParser(extracted):
    #initialization and parameters preparation
    Json_OBJ = {}

    Json_object = [0] * len(extracted.get('pages'))
    Json_OBJ['pages'] = Json_object

    dim = ['l','t','w','h']
    coord = ['x','y']

    Json_OBJ['fonts'] = []
    Font_Glossary = Json_OBJ['fonts']

    font_t = []

    #loops for distinct pages
    for page in range(len(extracted.get('pages'))):
        Json_object[page] = {}
        jsonobject = Json_object[page] #append each values in pages

        jsonobject['box'] = {}
        bbox = jsonobject['box']
        #loops for page details==========================================================================================
        for i in range(4):
            bbox[dim[i]] = extracted.get('pages')[page]['bbox'][i]

        jsonobject['rotation'] = {}
        rotbox = jsonobject['rotation']

        #details under 'rotation':====================================================================
        rotbox['degrees'] = angle(bbox['l'],bbox['t']) #usage of function "angle"

        rotbox['origin'] = {}
        originbox = rotbox['origin']
        for j in range(2):
            originbox[coord[j]] = bbox[dim[j+2]]/2

        rotbox['translation'] = {}
        transbox = rotbox['translation']
        for j in range(2):
            transbox[coord[j]] = bbox[dim[j]]/2
        #==============================================================================================
        jsonobject['pageNumber'] = raw.get('pages')[page]['pageno']

        jsonobject['element'] = []
        Elementdet = jsonobject['element']
        Element = {}
        #details under 'elements':=====================================================
        para_id = 1000 #counter for each paragraph id
        line_id = 2000 #counter for each line id
        word_id = 3000 #counter for each word id
        for k in range(len(raw.get('pages')[page]['careas'])):
            for l in range(len(raw.get('pages')[page]['careas'][k]['paragraphs'])):
                Specs = ['id','type', 'box', 'properties', 'content']
                for spec in Specs:
                    Element[spec] = {}

                parainfo = raw.get('pages')[page]['careas'][k]['paragraphs'][l]

                Element['id'] = para_id

                Element['type'] = 'paragraph'

                Element['box'] = {}
                jsonbox_form(Element['box'], dim, parainfo['bbox'])

                Element['properties'] = {}
                propel = Element['properties']
                propel['order'] = para_id

                Element['content'] = []
                Contdet = Element['content']
                ContEl = {}
                #details under 'content' of the 'elements'================================
                if 'lines' in parainfo.keys():
                    lineinfo = parainfo['lines']

                    for m in range(len(lineinfo)):

                        line_extract(ContEl, dim, lineinfo[m], line_id,'line')

                        ContEl['content'] = []
                        Linedet = ContEl['content']
                        Contline = {}
                        #details under 'line' 'content'=================
                        wordinfo = lineinfo[m]['words']
                        for n in range(len(wordinfo)):
                            word_extract(Contline, dim, wordinfo[n], Font_Glossary, font_t, word_id)
                            Linedet.append(Contline)
                            Contline = {}
                            word_id = word_id + 1
                        #===============================================

                        Contdet.append(ContEl)
                        ContEl = {}
                        line_id = line_id + 1

                elif 'headers' in parainfo.keys():
                    headerinfo = parainfo['headers']

                    for m in range(len(headerinfo)):

                        line_extract(ContEl, dim, headerinfo[m], line_id, 'header')

                        ContEl['content'] = []
                        Linedet = ContEl['content']
                        Contline = {}
                        #details under 'header' 'content'=================
                        wordinfo = headerinfo[m]['words']
                        for n in range(len(wordinfo)):
                            word_extract(Contline, dim, wordinfo[n], Font_Glossary, font_t, word_id)
                            Linedet.append(Contline)
                            Contline = {}
                            word_id = word_id + 1
                        #=================================================
                        Contdet.append(ContEl)
                        ContEl = {}
                        line_id = line_id + 1

                #=======================================================================
                para_id = para_id + 1 #counter for each paragraph id
                Elementdet.append(Element) #append each section to the 'Element' list
                Element = {}
        #===============================================================================================
        #===========================================================================================================

    return Json_OBJ


# In[65]:


#JSON file assembly and writing:
fileName = open("/home/ramoslee/work/EPOOPS/vahalla/PDFPatents/ES-1993/output-hocr/ES-2006680-B3-6.hocr", mode = 'r', encoding = "UTF-8") #fill in desired HOCR file for conversion
print(fileName)
extracted = HOCRParser(fs = fileName)
extracted.parse()
raw = extracted._parseddata
json_transformed = JsonFormParser(raw)
import json
with open('/home/ramoslee/work/EPOOPS/vahalla/PDFPatents/ES-1993/output-json/ES-2006680-B3-6-py-json','w') as outfile: #fill in the JSON file for writing
    json.dump(json_transformed,outfile)

