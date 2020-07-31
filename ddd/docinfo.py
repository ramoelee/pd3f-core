"""Statistics etc.
"""

from ddd.dehyphen import single_score
import logging
from collections import Counter
from statistics import median

from textdistance import jaccard

from .geometry import sim_bbox
from .utils import flatten

logger = logging.getLogger(__name__)


def avg_word_space(line):
    """Average word space on a line, util for words / lines
    
    src: https://github.com/axa-group/Parsr/blob/69e6b9bf33f1cc43d5a87d428cedf1132ccc48e8/server/src/types/DocumentRepresentation/Paragraph.ts#L460
    """

    def calc_margins(index, word):
        if index > 0:
            return word["box"]["l"] - (
                line["content"][index - 1]["box"]["l"]
                + line["content"][index - 1]["box"]["w"]
            )
        return 0

    margins = [calc_margins(i, w) for i, w in enumerate(line["content"])]
    return sum(margins) / len(margins)


def roughly_same_font(f1, f2):
    assert f1["sizeUnit"] == "px"
    assert f2["sizeUnit"] == "px"
    return abs(f1["size"] - f2["size"]) < max(f1["size"], f2["size"]) * 0.2


def extract_elements(outer_element, element_type):
    def traverse(element):
        if type(element) is dict:
            if "type" in element and element["type"] == element_type:
                return element
            if "content" in element:
                return traverse(element["content"])
            return None
        if type(element) is list:
            return [traverse(e) for e in element]

    return [
        x for x in flatten(traverse(outer_element), keep_dict=True) if x is not None
    ]


def font_stats(outer_element):
    return [x["font"] for x in extract_elements(outer_element, "word")]


def most_used_font(element):
    return Counter(font_stats(element)).most_common(1)[0][0]


def get_lineheight(l1, l2):
    # l1 or l2 can be the upper line
    if l2["box"]["t"] < l1["box"]["t"]:
        l1, l2 = l2, l1
    dif = l2["box"]["t"] - l1["box"]["t"] - l1["box"]["h"]
    # it may happen that the lines are on the same
    return dif if dif > 0 else None


def median_from_counter(c):
    data = []
    for value, count in c.most_common():
        data += [value] * count
    return median(data)


def only_text(es):
    r = []
    for e in es:
        for x in extract_elements(e, "word"):
            r.append(x["content"])
    return " ".join(r)


def only_points(es):
    r = []
    for e in es:
        b = e["box"]
        r.append((b["t"], b["l"]))
        r.append((b["t"] + b["h"], b["l"]))
        r.append((b["t"], b["l"] + b["w"]))
        r.append((b["t"] + b["h"], b["l"] + b["w"]))
    return r


def super_similiar(es1, es2, sim_factor=0.8, sim_box=0.6):
    """Check if two elements are super similiar by text (Jaccad) and visually (compare bbox).
    """
    text1 = only_text(es1)
    text2 = only_text(es2)

    points1 = only_points(es1)
    points2 = only_points(es2)
    j_sim = jaccard(text1, text2)
    b_sim = sim_bbox(points1, points2)

    logger.debug(f"footer/header sims {j_sim} {b_sim}")

    return j_sim > sim_factor and b_sim > sim_box


def remove_duplicates(page_items):
    results = [page_items[0]]
    for elements in page_items[1:]:
        cool = True
        for r in results:
            if len(r) == 0:
                continue
            # only choose the best first one?
            if super_similiar(r, elements):
                logger.debug("items are super similiar")
                if single_score(only_text(r)) < single_score(only_text(elements)):
                    logger.debug(
                        "okay, skipping here, the previous one got better score"
                    )
                    cool = False
                    break
                else:

                    logger.debug("removing previous one, this is better")
                    results.remove(r)

        if cool:
            results.append(elements)
        else:
            results.append([])
    return results


class DocumentInfo:
    def __init__(self, input_data) -> None:
        self.input_data = input_data

        # needs to be done first
        self.element_order_page()
        self.document_font_stats()
        self.document_paragraph_stats()

        # free memory (code should have been re-written but whatehver)
        del self.input_data

    def document_paragraph_stats(self):
        """
        """

        def calc_line_space(lines):
            if len(lines) <= 1:
                return []
            lineheights = []
            for i, _ in enumerate(lines[:-1]):
                if (x := get_lineheight(lines[i], lines[i + 1])) is not None:
                    lineheights.append(x)
            return lineheights

        self.counter_width = Counter()
        self.counter_height = Counter()
        self.counter_lineheight = Counter()

        for n_page, p in enumerate(self.input_data["pages"]):
            for e in p["elements"]:
                lis = extract_elements(e, "line")
                for x in lis:
                    x["page_num"] = n_page
                    self.id_to_elem[x["id"]] = x

                self.counter_width.update([x["box"]["w"] for x in lis])
                self.counter_height.update([x["box"]["h"] for x in lis])
                self.counter_lineheight.update(calc_line_space(lis))

        self.median_line_width = median_from_counter(self.counter_width)
        self.median_line_height = median_from_counter(self.counter_height)
        # line space: line height
        self.median_line_space = median_from_counter(self.counter_lineheight)

        logger.info(f"media line width: {self.median_line_width}")
        logger.info(f"median line height: {self.median_line_height}")
        logger.info(f"median line space: {self.median_line_space}")
        logger.info(f"counter width: {self.counter_width.most_common(5)}")
        logger.info(f"counter height: {self.counter_height.most_common(5)}")
        logger.info(f"counter lineheight: {self.counter_lineheight.most_common(5)}")

    def document_font_stats(self):
        """Get statistics about font usage in the document
        """
        c = Counter()
        for p in self.input_data["pages"]:
            for e in p["elements"]:
                c.update(font_stats(e))
        self.body_font = c.most_common(1)[0][0]
        self.font_counter = c
        self.font_info = {}
        for x in self.input_data["fonts"]:
            self.font_info[x["id"]] = x
            assert x["sizeUnit"] == "px"

    def seperate_lines(self, l1, l2, factor=0.5):
        lh = get_lineheight(l1, l2)
        if lh is None:
            return False
        # space between lines can only be + 0.5x the body lineheight
        return ((lh - self.median_line_space) / self.median_line_space) > factor

    def on_same_page(self, e1, e2):
        """Check if both elements are on the same page
        """
        return (
            self.id_to_elem[e1["id"]]["page_num"]
            == self.id_to_elem[e2["id"]]["page_num"]
        )

    def element_order_page(self):
        """Save the order of paragraphes for each page
        """
        self.order_page = []
        self.id_to_elem = {}
        for n_page, p in enumerate(self.input_data["pages"]):
            per_page = []
            for e in p["elements"]:
                # not all elements are included here
                e["page_num"] = n_page
                self.id_to_elem[e["id"]] = e

                if not e["type"] in ("paragraph", "heading"):
                    continue
                if "isHeader" in e["properties"] and e["properties"]["isHeader"]:
                    continue
                if "isFooter" in e["properties"] and e["properties"]["isFooter"]:
                    continue

                per_page.append(e["id"])
            self.order_page.append(per_page)
