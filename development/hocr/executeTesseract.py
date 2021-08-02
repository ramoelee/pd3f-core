#!/usr/bin/python3

import subprocess
import argparse


class Tesseract(object):
  def __init__(self, lang):
    self.lang = lang
    cmd = ["tesseract", "stdin", "stdout", "-l", self.lang, "-c", "hocr_char_boxes=1", "hocr"]
    f_stderr = open("/dev/null")
    self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

  def process(self, filepaths):
    input_string = filepaths
    input_string = input_string.encode("utf-8")
    print(input_string)
    self.proc.stdin.write(input_string)
    self.proc.stdin.flush()
    self.proc.stdin.close()
    print("read stdout:")
    # result = self.proc.stdout.
    result = "";
    while True:
        output = self.proc.stdout.readline()
        if output.decode("utf-8").strip() == '' and self.proc.poll() is not None:
            break
        else:
            result = result + "\n" + output.decode("utf-8").strip()
        # if output:
        #     print(output.decode("utf-8").strip())

        # if "</html>" == output.decode("utf-8").strip():
        #     print("Last LINE")

    print("Done read stdout:")
    # print(result)
    return result

# parser = argparse.ArgumentParser(description='Command line tool for Get hocr file from images.')
# parser.add_argument('--lang', help='Tesseract language id')
# parser.add_argument('--input', help='Input file paths')
# parser.add_argument('--output', help='Output file path')
# args = parser.parse_args()
# args.lang = "spa"
# args.input =  "/home/ramoslee/work/EPOOPS/vahalla/PDFPatents/ES-1993/output-img/ES-2006680-B3-6-1.pdf1.jpg\n"

# if not args.lang:
#     raise Exception("ERROR: Please specify Tesseract language.")
#
# if not args.input:
#     raise Exception("ERROR: Please specify input.")

# tesseract = Tesseract(["tesseract","stdin","stdout", "-l", args.lang, "-c", "hocr_char_boxes=1", "hocr"])
# tesseract = Tesseract(args.lang)
# filepahts = args.input;
# hocr = tesseract.process(filepahts)
# print(hocr)


