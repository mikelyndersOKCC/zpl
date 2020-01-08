#!/usr/bin/env python

from __future__ import division
from __future__ import print_function

#import Image
from PIL import Image
import re
import PIL.ImageOps
import sys
import math
import webbrowser
import os.path
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen
import io

class Label:
    '''
    Used to build a ZPL2 label.

    all dimensions are given in millimeters and automatically converted to
    printer dot units.
    '''

    def __init__(self, height, width=110.0, dpmm=12.0, rotate_180=False):
        """
        Creates one (or more) ZPL2 labels.

        *height* and *width* are given in millimeters
        *dpmm* refers to dots per millimeter (e.g. 12 for 300dpi)
        """
        self.height = height
        self.width = width
        self.dpmm = dpmm

        self.code = "^XA"

        if rotate_180: self.code += "^POI"

    def origin(self, x,y):
        """
        new block located at x and y (in millimeters)
        """
        self.code += "^FO%i,%i" % (x*self.dpmm, y*self.dpmm)

    def endorigin(self):
        self.code += '^FS'

    def textblock(self, width, justification='C', lines=1):
        """
        new text block

        width of textblock in millimeters
        """
        assert justification in ['L','R','C','J']
        self.code += "^FB%i,%i,%i,%s,%i" % (width*self.dpmm, lines, 0, justification, 0)

    def write_text(self, text, char_height=None, char_width=None, font='0', orientation='N',
                   line_width=None, max_line=1, line_spaces=0, justification='L', hanging_indent=0):
        if char_height and char_width and font and orientation:
            assert orientation in 'NRIB', "invalid orientation"
            if re.match(r'^[A-Z0-9]$', font):
                self.code += "^A%c%c,%i,%i" % (font, orientation, char_height*self.dpmm,
                                               char_width*self.dpmm)
            elif re.match(r'[REBA]?:[A-Z0-9\_]+\.(FNT|TTF|TTE)', font):
                self.code += "^A@%c,%i,%i,%s" % (orientation, char_height*self.dpmm,
                                               char_width*self.dpmm, font)
            else:
                raise ValueError("Invalid font.")
        if line_width:
            assert justification in "LCRJ", "invalid justification"
            self.code += "^FB%i,%i,%i,%c,%i" % (line_width*self.dpmm, max_line, line_spaces,
                                                justification, hanging_indent)
        self.code += "^FD%s" % text

    def set_default_font(self, height, width, font='0'):
        """
        sets default font from here onward

        height and width are given in milimeters
        """
        assert re.match(r'[A-Z0-9]', font), "invalid font"
        self.code += "^CF%c,%i,%i" % (font, height*self.dpmm, width*self.dpmm)

    def _convert_image(self, image, width, height, compression_type='A'):
        '''
        converts *image* (of type PIL.Image) to a ZPL2 format

        compression_type can be one of ['A', 'B', 'C']

        returns data
        '''
        image = image.resize((int(width*self.dpmm), int(height*self.dpmm)))
        # invert, otherwise we get reversed B/W
        # https://stackoverflow.com/a/38378828
        image = PIL.ImageOps.invert(image.convert('L')).convert('1')

        if compression_type == "A":
            # return image.tobytes().encode('hex').upper()
            return image.tobytes().hex().upper()
        # TODO this is not working
        #elif compression_type == "B":
        #    return image.tostring()
        else:
            raise Exception("unsupported compression type")


    def upload_graphic(self, name, image, width, height=0):
        """in millimeter"""
        if not height:
            height = int(float(image.size[1])/image.size[0]*width)

        assert 1 <= len(name) <= 8, "filename must have length [1:8]"

        totalbytes = math.ceil(width*self.dpmm/8.0)*height*self.dpmm
        bytesperrow = math.ceil(width*self.dpmm/8.0)

        data = self._convert_image(image, width, height)

        self.code += "~DG%s.GRF,%i,%i,%s" % (name, totalbytes, bytesperrow, data)

        return height

    def write_graphic(self, image, width, height=0, compression_type="A"):
        """
        embeddes image with given width

        image has to be of type PIL.Image
        if height is not given, it will be chosen proportionally
        """
        if not height:
            height = int(float(image.size[1])/image.size[0]*width)

        totalbytes = math.ceil(width*self.dpmm/8.0)*height*self.dpmm
        bytesperrow = math.ceil(width*self.dpmm/8.0)

        data = self._convert_image(image, width, height, compression_type=compression_type)

        if compression_type == "A":
            self.code += "^GFA,%i,%i,%i,%s" % (len(data), totalbytes, bytesperrow, data)
        # TODO this is not working:
        elif compression_type == "B":
            self.code += "^GFB,%i,%i,%i,%s" % (len(data), totalbytes, bytesperrow, data)
        else:
            raise Exception("Unsupported compression type.")

        return height

    def draw_box(self, width, height, thickness=1, color='B', rounding=0):
        assert color in 'BW', "invalid color"
        assert rounding <= 8, "invalid rounding"
        self.code += "^GB,%i,%i,%i,%c,%i" % (width, height, thickness, color, rounding)

    def draw_ellipse(self, width, height, thickness=1, color='B'):
        assert color in 'BW', "invalid color"
        self.code += "^GE,%i,%i,%i,%c" % (width, height, thickness, color)

    def print_graphic(self, name, scale_x=1, scale_y=1):
        self.code += "^XG%s,%i,%i" % (name, scale_x, scale_y)

    def run_script(self, filename):
        self.code += "^XF%s^FS"

    def write_field_number(self, number, name=None, char_height=None, char_width=None, font='0',
                           orientation='N', line_width=None, max_line=1, line_spaces=0,
                           justification='L', hanging_indent=0):
        if char_height and char_width and font and orientation:
            assert re.match(r'[A-Z0-9]', font), "invalid font"
            assert orientation in 'NRIB', "invalid orientation"
            self.code += "^A%c%c,%i,%i" % (font, orientation, char_height*self.dpmm,
                                           char_width*self.dpmm)
        if line_width:
            assert justification in "LCRJ", "invalid justification"
            self.code += "^FB%i,%i,%i,%c,%i" % (line_width*self.dpmm, max_line, line_spaces,
                                                justification, hanging_indent)
        self.code += "^FN%i" % number
        if name:
            assert re.match("^[a-zA-Z0-9 ]+$", name), "name may only contain alphanumerical " + \
                "characters and spaces"
            self.code += '"%s"' % name

    def write_barcode(self, height, barcode_type, orientation='N', check_digit='N',
                       print_interpretation_line='Y', print_interpretation_line_above='N', thin_bar_width=None):
        # guard for only currently allowed bar codes
        assert barcode_type in ['2', '3', 'U'], "invalid barcode type"

        if barcode_type == '2':
            barcode_zpl = '^B%s%s,%i,%s,%s,%s' % (barcode_type, orientation, height,
                                                   print_interpretation_line,
                                                   print_interpretation_line_above,
                                                   check_digit)
        elif barcode_type == '3':
            barcode_zpl = '^B%s%s,%s,%i,%s,%s' % (barcode_type, orientation,
                                                   check_digit, height,
                                                   print_interpretation_line,
                                                   print_interpretation_line_above)
        elif barcode_type == 'U':
            barcode_zpl = '^B%s%s,%s,%s,%s,%s' % (barcode_type, orientation, height,
                                                   print_interpretation_line,
                                                   print_interpretation_line_above,
                                                   check_digit)

        bar_width_modifier = '^BY%s' % (thin_bar_width) if thin_bar_width else ""

        self.code += bar_width_modifier + barcode_zpl

    def dumpZPL(self):
        return self.code+"^XZ"

    def saveFormat(self, name):
        self.code= self.code[:3] + ("^DF%s^FS" % name) + self.code[3:]

    def preview(self, index=0):
        '''
        Opens rendered preview using Labelary API.

        Not all commands are supported, see http://labelary.com for more information.
        '''
        try:
            url = 'http://api.labelary.com/v1/printers/%idpmm/labels/%fx%f/%i/' % (
                self.dpmm, self.width/25.4, self.height/25.4, index)
            res = urlopen(url, self.dumpZPL().encode()).read()
            Image.open(io.BytesIO(res)).show()
        except IOError:
            raise Exception("Invalid preview received, mostlikely bad ZPL2 code uploaded.")


def __main__():
    serial_number = '12345-1'
    image_path = "BLP-wf"
    job_number = "M043737"
    part_number = "OKC-2975"

    left_margin = 0

    label = Label(65,90)

    label.origin(left_margin,20)
    label.write_text(f"PN: {part_number}", char_height=5, char_width=4,justification='L')
    label.endorigin()

    label.origin(left_margin,25)
    label.write_barcode(height=50, barcode_type='3', print_interpretation_line='N', thin_bar_width='3')
    label.write_text(part_number)
    label.endorigin()

    label.origin(left_margin,30)
    label.write_text(f"QTY: 1", char_height=5, char_width=4,justification='L')
    label.endorigin()

    label.origin(left_margin,35)
    label.write_text(f"Lot #: {job_number}", char_height=5, char_width=4,justification='L')
    label.endorigin()

    label.origin(left_margin,40)
    label.write_barcode(height=50, barcode_type='3', print_interpretation_line='N', thin_bar_width='3')
    label.write_text(job_number)
    label.endorigin()

    label.origin(left_margin,45)
    label.write_text(f"SN: {serial_number}", char_height=5, char_width=4,justification='L')
    label.endorigin()


    label.origin(50,35)
    label.write_graphic(Image.open('/home/mikelynders/part_images/' + image_path + '.bmp'), 35)
    label.endorigin()

    print(label.dumpZPL())
    label.preview()

    


if __name__ == "__main__":
    __main__()
