##########################################################################
# NSAp - Copyright (C) CEA, 2016
# Distributed under the terms of the CeCILL-B license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL-B_V1-en.html
# for details.
##########################################################################


# System import
import base64
import json
import os
import nibabel
import numpy
from PIL import Image

# CW import
from cubicweb import _
from cubicweb.view import View
from cubicweb.web.views.ajaxcontroller import ajaxfunc
from cubicweb.predicates import authenticated_user


###############################################################################
# Display a stack of images as a triplanar view
###############################################################################

class TriplanarStackViewer(View):
    """ Dynamic volume slicer from 'coronal', 'axial' and 'sagittal' stacks.
    """
    __regid__ = "triplanar-stack-viewer"
    __select__ = authenticated_user()
    templatable = False
    # This message will be formated with the snap eid
    error_message = ("Triplanar view not responding. Please contact the "
                     "service administrator specifying the the snap code "
                     "'{0}'.")

    def call(self): #, snap_eid, file_data, data_type):
        """ Create the viewer: orign is at the bottom left corner of the image,
        thus the stack ordering must be:
        axial: I->S
        coronal: P->A
        sagittal: L->R

        Depending on your data, the loading time can be quite important, thus
        all the button with a 'triview-btn' class will be disabled during
        this step.

        The code can display a single, two or three orientations view.

        Parameters
        ----------
        snap_eid: Entity (mandatory)
            the snap CW entity eid.
        file_data: dict (mandatory)
            the 'coronal', 'axial' and 'sagittal' stack names as keys with
            a list of ordered image files as value.
        data_type: str (mandatory)
            the image to display extension.
        """
        # Define parameters
        snap_eid = self._cw.form["snap_eid"]
        file_data = json.loads(self._cw.form["file_data"])
        data_type = self._cw.form["data_type"]
        error = self.error_message.format(snap_eid)
        brightness = 100

        # Add JS and CSS resources for the sliders and triview
        self.w(u'<script type="text/javascript" '
                'src="https://ajax.googleapis.com/ajax/libs/jquery/1.12.0/'
                'jquery.min.js"></script>')
        for path in ("triview/js/simple-slider.min.js",
                     "triview/js/triview.js"):
            href = self._cw.data_url(path)
            self.w(u'<script type="text/javascript" src="{0}"></script>'.format(href))
        for path in ("triview/css/simple-slider-volume.css",
                     "triview/css/triview.css"):
            href = self._cw.data_url(path)
            self.w(u'<link type="text/css" rel="stylesheet" href="{0}">'.format(href))

        # Check inputs
        orientations = ["sagittal", "coronal", "axial"]
        shapes = {}
        nb_slices = {}
        for orient in file_data:
            # > check orientation
            if orient not in orientations:
                self.w(u"<h1>{0}</h1>".format(error))
                self.w(u"<script>")
                self.w(u"disableTriViewBtn();")
                self.w(u"</script>")
                return
            # > check image sizes
            stack_size = None
            nb_slices[orient] = len(file_data[orient]) - 1
            for path in file_data[orient]:
                with Image.open(path) as open_image:
                    if stack_size is None:
                        stack_size = open_image.size
                        shapes[orient] = stack_size
                    elif stack_size != open_image.size:
                        self.w(u"<h1>{0}</h1>".format(error))
                        self.w(u"<script>")
                        self.w(u"disableTriViewBtn();")
                        self.w(u"</script>")
                        return

        # Add an hidden loading image
        html = "<div id='loading-msg' style='display: none;' align='center'>"
        loading_img_url = self._cw.data_url("triview/load.gif")
        html += "<img src='{0}'/>".format(loading_img_url)
        html += "</div>"

        # Add viewer containers
        html += "<div class='container'>"
        # > create the brightness horizontal scroll bar
        html += "<div>"
        html += "<h4 style='color: white;'>BRIGHTNESS</h4>"
        html += ("<input id='brightness-bar' type='text' "
                 "data-slider='true' data-slider-range='0,200' "
                 "value='100' data-slider-step='1' "
                 "data-slider-highlight='true' "
                 "data-slider-theme='volume'>")
        html += ("<p id='brightness-bar-text' style='color: "
                 "white;margin-bottom: 50px;'>{0} %</p>".format(brightness))
        html += "</div>"
        # > create image containers
        for orient, shape in shapes.items():
            html += "<div id='{0}' class='subdiv'>".format(orient)
            html += "<h4 style='color: white;'>{0}</h4>".format(
                orient.upper())
            html += ("<input class='slice-bar' type='text' data-slider='true' "
                     "data-slider-range='0,{0}' value='{1}' "
                     "data-slider-step='1' data-slider-highlight='true' "
                     "data-slider-theme='volume'>".format(
                         nb_slices[orient], nb_slices[orient] // 2))
            html += ("<p class='slice-bar-text' style='color: white;'>"
                     "{0} / {1}</p>".format(
                         nb_slices[orient] // 2, nb_slices[orient]))
            html += ("<canvas class='slice-img' width='{0}' height='{1}'>"
                     "</canvas>".format(shape[0], shape[1]))
            html += "</div>"
        html += "</div>"

        # Construct the data accessor url
        ajaxcallback = self._cw.build_url("ajax", fname="get_b64_images")

        # Create javascript global variables
        triview_data = {
            "dtype": data_type.lower(),
            "file_data": file_data,
            "ajaxcallback": ajaxcallback,
            "orientations": file_data.keys(),
            "brightness": 100,
            "shapes": shapes,
            "nb_slices": nb_slices}
        html += "<script>"
        html += "var triview_data = {0};".format(json.dumps(triview_data))
        html += "</script>"

        # Initilaize the viewer
        html += "<script>"
        html += "$(document).ready(function() {"
        html += "disableTriViewBtn();"
        html += "initTriViewGui();"
        html += "});"
        html += "</script>"

        # Set page code
        self.w(unicode(html))


@ajaxfunc(output_type="json")
def get_b64_images(self):
    """ Ajax callback used to load images in the 'file_data' form in base64.
    """
    file_data = json.loads(self._cw.form["file_data"])
    output = {}
    for orient, fpaths in file_data.items():
        encoded_images = []
        for path in fpaths:
            with open(path, "rb") as open_image:
                encoded_image = base64.b64encode(open_image.read())
                encoded_images.append(encoded_image)
        output[orient] = encoded_images
    return output


###############################################################################
# Display a 3D or 4D image as a triplanar view
###############################################################################

class TriplanarImageViewer(View):
    """ Create an image viewer.
    """
    __regid__ = "triplanar-image-viewer"
    __select__ = authenticated_user()
    title = _("Brainbrowser")
    templatable = False
    paginable = False
    div_id = "brainbrowser-simple"

    def __init__(self, *args, **kwargs):
        """ Initialize the ImageViewer class.

        If you want to construct the viewer manually in your view pass the
        parent view in the 'parent_view' attribute.
        """
        super(TriplanarImageViewer, self).__init__(*args, **kwargs)
        if "parent_view" in kwargs:
            self._cw = kwargs["parent_view"]._cw
            self.w = kwargs["parent_view"].w

    def call(self, imagefiles=None, **kwargs):
        """ Method that will create a simple BrainBrowser image viewer.

        Parameters
        ----------
        imagefiles: list of str (mandatory)
            the path to the paths that will be rendered.
        """
        # Get the parameters
        imagefiles = imagefiles or self._cw.form.get("imagefiles", "")

        # Guarantee that we have a list of paths
        if not isinstance(imagefiles, list):
            imagefiles = [imagefiles]

        # Get the path to the in progress resource
        wait_image_url = self._cw.data_url("images/please_wait.gif")

        # Add css resources
        for path in ("brainbrowser/css/ui-darkness/jquery-ui-1.8.10.custom.css",
                     "brainbrowser/css/common.css",
                     "zeijemol.triplanar.css"):
            href = self._cw.data_url(path)
            self.w(u'<link type="text/css" rel="stylesheet" href="{0}">'.format(href))

        # Add js resources
        for path in ("brainbrowser/src/jquery-1.6.4.min.js",
                     "brainbrowser/src/jquery-ui-1.8.10.custom.min.js",
                     "brainbrowser/src/ui.js",
                     "brainbrowser/src/brainbrowser/brainbrowser.js",
                     "brainbrowser/src/brainbrowser/core/tree-store.js",
                     "brainbrowser/src/brainbrowser/lib/config.js",
                     "brainbrowser/src/brainbrowser/lib/utils.js",
                     "brainbrowser/src/brainbrowser/lib/events.js",
                     "brainbrowser/src/brainbrowser/lib/loader.js",
                     "brainbrowser/src/brainbrowser/lib/color-map.js",
                     "brainbrowser/src/brainbrowser/volume-viewer.js",
                     "brainbrowser/src/brainbrowser/volume-viewer/lib/display.js",
                     "brainbrowser/src/brainbrowser/volume-viewer/lib/panel.js",
                     "brainbrowser/src/brainbrowser/volume-viewer/lib/utils.js",
                     "brainbrowser/src/brainbrowser/volume-viewer/modules/loading.js",
                     "brainbrowser/src/brainbrowser/volume-viewer/modules/rendering.js",
                     "brainbrowser/src/brainbrowser/volume-viewer/volume-loaders/overlay.js",
                     "brainbrowser/src/brainbrowser/volume-viewer/volume-loaders/minc.js",
                     "zeijemol.triplanar.js"):
            href = self._cw.data_url(path)
            self.w(u'<script type="text/javascript" src="{0}"></script>'.format(href))

        # Set the brainbrowser viewer navigation tools
        html = self.build_brainbrowser_tools()

        # Create a div for the in progress resource
        html += ("<div id='loading' style='display:none' align='center'>"
                 "<img src='{0}'/></div>".format(wait_image_url))

        # Build a brainborwser banner with tools
        html += self.build_brainbrowser_banner(imagefiles)

        # Set brainbrowser colormaps
        html += self.build_color_maps()

        # Define global javascript variables
        html += "<script type='text/javascript'>"
        html += "var quality = 50;"
        html += "var ajaxcallback = 'get_brainbrowser_image';"
        html += "</script>"

        # Set brainbrowser nifti image loader
        html += self.build_nifti_image_loader()

        # Set a callback to select the qulity of the rendering
        html += self.build_quality_callback(imagefiles)

        # Set a callback to select an image to render
        html += self.build_image_callback(imagefiles)

        # Set a callback to select the rendering
        html += self.build_rendering_callback(imagefiles)

        # Set the cw brainbrowser image loader
        html += self.build_cw_loader(imagefiles, 0, True)

        html += '<div id="zeijemol-credits">'
        html += '<strong>BrainBrowser&#169; visualisation tool :</strong>'
        html += '<dl class="dl-horizontal">'
        html += '<dt>Lead Developer</dt><dd>Tarek Sherif</dd>'
        html += '<dt>Full credits</dt><dd><a href="https://brainbrowser.cbrain.mcgill.ca/">BrainBrowser Website</a></dd>'
        html += '</dl>'
        html += '<div>'

        # Creat the corresponding html page
        self.w(unicode(html))

    def build_nifti_image_loader(self):
        """ Define a nifti image loader for BrainBrowser based on a CubicWeb
        ajax callback.

        Returns
        -------
        html: str
            the nifti loader definition.
        """
        # Add javascript
        html = "<script type='text/javascript'>"

        # And create the appropriate viewer
        html += "var VolumeViewer = BrainBrowser.VolumeViewer;"
        html += ("VolumeViewer.volume_loaders.nifti = "
                 "function(description, callback) {")

        # Display wait message
        html += "$('#loading').show();"

        # Execute the ajax callback
        html += "var postData = {};"
        html += "postData.imagefile = description.data_file;"
        html += "postData.dquality = quality;"
        html += "var post = $.ajax({"
        html += "url: '{0}ajax?fname=' + ajaxcallback,".format(
            self._cw.base_url())
        html += "type: 'POST',"
        html += "data: postData"
        html += "});"

        # The ajax callback is done, get the result set
        html += "post.done(function(p){"
        html += "$('#loading').hide();"
        html += "var data = p.data;"
        html += "var header_text = p.header;"

        # Decode and display data: expect uint8 buffer
        html += "if (ajaxcallback == 'get_encoded_brainbrowser_image') {"

        # Create the flatten image array data
        html += "var slice_cnt = 0;"
        html += "var the_array = [];"
        html += "data.forEach(function(slicedata, slice_cnt) {"

        # Decode the image in a function where a callback is called and
        # and executed when the buffer is properly filled
        html += "var effect = function(slicedata, length, callback) {"
        html += "var img = new Image();"
        html += "img.onload = function() {"
        html += "var canvas = document.createElement('canvas');"
        html += "canvas.width  = img.width;"
        html += "canvas.height = img.height;"
        html += "var ctx = canvas.getContext('2d');"
        html += "ctx.drawImage(img, 0, 0);"
        html += "var imageData = ctx.getImageData(0,0,canvas.width, canvas.height);"
        html += "var slicedata = imageData.data;"

        # Fill the buffer: use scale factor to match uint16 dynamic
        html += "for (var j = 0; j < slicedata.length; j += 4) {"
        html += "the_array.push(slicedata[j] * 257);"
        html += "}"

        # Call the callback that will render the image when the buffer is
        # completed
        html += "callback(the_array, (slice_cnt + 1) == length);"

        # Close onload
        html += "};"

        # Set the current slice base64 source
        html += "img.src = 'data:image/jpg;base64,' + slicedata;"

        # Close effect
        html += "};"

        # Load the image and define the callback
        html += "effect(slicedata, data.length, function(data, is_loaded) {"

        # Test if all the slice have been loaded in the buffer
        html += "if (is_loaded) {"

        # Load the image in BrainBrowsers
        html += "var error_message;"
        html += "if (description.data_file) {"
        html += "BrainBrowser.parseHeader(header_text, function(header) {"
        html += "BrainBrowser.createMincVolume(header, data, callback);"
        html += "});"
        html += "error_message = header.xspace.name;"
        html += ("BrainBrowser.events.triggerEvent('error', "
                 "{ message: error_message });")
        html += "throw new Error(error_message);"
        html += "} else {"
        html += "error_message = 'Error';"
        html += ("BrainBrowser.events.triggerEvent('error', "
                 "{ message: error_message });")
        html += "throw new Error(error_message);"
        html += "}"

        # Close callback
        html += "};"
        html += "});"

        # Close foreach
        html += "});"

        # Close if encoded
        html += "}"

        # Display data: expect uint16 buffer
        html += "else {"

        # Load the image in BrainBrowsers
        html += "var error_message;"
        html += "if (description.data_file) {"
        html += "BrainBrowser.parseHeader(header_text, function(header) {"
        html += "BrainBrowser.createMincVolume(header, data, callback);"
        html += "});"
        html += "error_message = header.xspace.name;"
        html += ("BrainBrowser.events.triggerEvent('error', "
                 "{ message: error_message });")
        html += "throw new Error(error_message);"
        html += "} else {"
        html += "error_message = 'Error';"
        html += ("BrainBrowser.events.triggerEvent('error', "
                 "{ message: error_message });")
        html += "throw new Error(error_message);"
        html += "}"

        # Close else
        html += "}"

        # Close post
        html += "});"

        # Error when the loading failed
        html += "post.fail(function(){"
        html += "$('#loading').hide();"
        html += " alert('Error : Image buffering failed!');"
        html += "});"

        html += "};"

        # Close javascript
        html += "</script>"

        return html

    def build_cw_loader(self, imagefiles, index=0, decorated=False,
                        multiview=False):
        """ Define the script that will load the image in BrainBrowser.

        Parameters
        ----------
        imagefiles: list of str (mandatory)
            the path to the paths that will be rendered.
        index: int (optional, default 0)
            the index of the image to render.
        decorated: bool (optional, default False)
            add the javascript tag.
        multiview: bool (optional, default False)
            display all the images at the same time.

        Returns
        -------
        html: str
            the loader definition.
        """
        # Add javascript
        html = ""
        if decorated:
            html += "<script type='text/javascript'>"
        html += "$(document).ready(function() {"

        # Load the volume
        html += "var viewer = window.viewer;"
        if multiview:
            html += "viewer.loadVolumes({"
            html += "volumes: ["
            for path in imagefiles:
                html += "{"
                html += "type: 'nifti',"
                html += "data_file: '{0}',".format(path)
                html += "template: {"
                html += "element_id: 'volume-ui-template',"
                html += "viewer_insert_class: 'volume-viewer-display'"
                html += "}"
                html += "},"
            html += "],"
            html += "complete: function() {"
            html += "$('#volume-type').hide();"
            html += "$('.slice-display').css('display', 'inline');"
            html += "$('.volume-controls').css('width', 'auto');"
            html += "$('#loading').hide();"
            html += "$('#brainbrowser-wrapper').slideDown({duration: 600});"
            html += "}"
            html += "});"
        else:
            html += "viewer.loadVolume({"
            html += "type: 'nifti',"
            html += "data_file: '{0}',".format(imagefiles[index])
            html += "template: {"
            html += "element_id: 'volume-ui-template',"
            html += "viewer_insert_class: 'volume-viewer-display'"
            html += "}"
            html += "}, function() {"
            html += "$('#volume-type').show();"
            html += "$('.slice-display').css('display', 'inline');"
            html += "$('.volume-controls').css('width', 'auto');"
            html += "$('#loading').hide();"
            html += "$('#brainbrowser-wrapper').slideDown({duration: 600});"
            html += "});"

        # Close function
        html += "});"

        # Close javascript
        if decorated:
            html += "</script>"

        return html

    def build_quality_callback(self, imagefiles):
        """ Define the rendering quality callback.

        Parameters
        ----------
        imagefiles: list of str (mandatory)
            the path to the images that will be rendered.

        Returns
        -------
        html: str
            the quality definition.
        """
        # Add javascript
        html = "<script type='text/javascript'>"

        # Define the callback
        html += "$('#volume-quality').change(function() {"

        # Raw data are requested
        html += "if ($('#volume-quality').val() === 'RAW') {"
        html += "ajaxcallback = 'get_brainbrowser_image';"
        html += "}"

        # Low quality encoded data are requested
        html += "else if ($('#volume-quality').val() === 'LOW JPEG') {"
        html += "ajaxcallback = 'get_encoded_brainbrowser_image';"
        html += "quality = 50;"
        html += "}"

        # Add out of range event
        html += "else {"
        html += "ajaxcallback = 'get_brainbrowser_image';"
        html += "}"

        # Show the new image representation
        html += self.build_image_callback(imagefiles, False)

        # Close callback function
        html += "});"

        # Close javascript
        html += "</script>"

        return html

    def build_rendering_callback(self, imagefiles):
        """ Define the rendering callback.

        Parameters
        ----------
        imagefiles: list of str (mandatory)
            the path to the images that will be rendered.

        Returns
        -------
        html: str
            the rendering definition.
        """
        # Add javascript
        html = "<script type='text/javascript'>"

        # Define the callback
        html += "$('#volume-rendering').change(function() {"

        # Add an event when an event occur
        html += self.build_image_callback(imagefiles, False)

        # Close callback function
        html += "});"

        # Close javascript
        html += "</script>"

        return html

    def build_image_callback(self, imagefiles, decorated=True):
        """ Define the on image change callback.

        Parameters
        ----------
        imagefiles: list of str (mandatory)
            the path to the paths that will be rendered.
        decorated: bool (optional, default True)
            add the javascript tag.

        Returns
        -------
        html: str
            the callback definition.
        """
        # Add javascript
        html = ""
        if decorated:
            html += "<script type='text/javascript'>"

            # Define the callback
            html += "$('#volume-type').change(function() {"

        # Add an event for each image
        for cnt in range(len(imagefiles)):
            if cnt == 0:
                html += "if ($('#volume-type').val() === '{0}') {{".format(cnt)
            else:
                html += "else if ($('#volume-type').val() === '{0}') {{".format(cnt)
            html += "viewer.clearVolumes();"
            html += "if ($('#volume-rendering').val() == 'multi') {"
            html += self.build_cw_loader(imagefiles, cnt, multiview=True)
            html += "}"
            html += "else {"
            html += self.build_cw_loader(imagefiles, cnt, multiview=False)
            html += "}"
            html += "}"

        # Add out of range event
        html += "else {"
        html += "viewer.clearVolumes();"
        html += "}"

        if decorated:
            # Close callback function
            html += "});"

            # Close javascript
            html += "</script>"

        return html

    def build_color_maps(self):
        """ Define the BrainBrowser color-maps.

        Returns
        -------
        html: str
            the color-maps definition.
        """
        # Go through colormaps
        html = "<script>"
        html += "BrainBrowser.config.set('color_maps', ["
        baseurl = "brainbrowser/color-maps/"
        for name, color in [("Gray", "#FF0000"), ("Spectral", "#FFFFFF"),
                            ("Thermal", "#FFFFFF"), ("Blue", "#FFFFFF"),
                            ("Green", "#FF0000")]:
            resource = self._cw.data_url(
                os.path.join(baseurl, "{0}.txt".format(name.lower())))

            html += "{"
            html += "name: '{0}',".format(name)
            html += "url: '{0}',".format(resource)
            html += "cursor_color: '{0}'".format(color)
            html += "},"
        html += "]);"
        html += "</script>"

        return html

    def build_brainbrowser_tools(self, time=True, contrast=False,
                                 brightness=False):
        """ Define the default BrainBrowser tools.

        Parameters
        ----------
        time: bool (optional, default False)
            add control to display time serie images.
        contrast, brightness: bool (optional, default False)
            add extra controls (not recommended).

        Returns
        -------
        html: str
            the tools definition.
        """
        # Start javascript
        html = "<script id='volume-ui-template' type='x-volume-ui-template'>"

        # Define the image rendering location
        html += "<div class='volume-viewer-display'>"
        html += "</div>\n"

        # Define control tools
        html += "<div class='volume-viewer-controls volume-controls'>"

        # Define a tool to display the voxel and world coordinates
        html += "<div class='coords'>"
        html += "<div class='control-container'>"
        html += ("<div class='control-heading' "
                 "id='voxel-coordinates-heading-{{VOLID}}'>")
        html += "Voxel Coordinates:"
        html += "</div>"
        html += "<div class='voxel-coords' data-volume-id='{{VOLID}}'>"
        html += "I:<input id='voxel-i-{{VOLID}}' class='control-inputs'>"
        html += "J:<input id='voxel-j-{{VOLID}}' class='control-inputs'>"
        html += "K:<input id='voxel-k-{{VOLID}}' class='control-inputs'>"
        html += "</div>"
        html += ("<div class='control-heading' "
                 "id='world-coordinates-heading-{{VOLID}}'>")
        html += "World Coordinates:"
        html += "</div>"
        html += "<div class='world-coords' data-volume-id='{{VOLID}}'>"
        html += "X:<input id='world-x-{{VOLID}}' class='control-inputs'>"
        html += "Y:<input id='world-y-{{VOLID}}' class='control-inputs'>"
        html += "Z:<input id='world-z-{{VOLID}}' class='control-inputs'>"
        html += "</div>"

        # Define a tool to control different images in the volume
        if time:
            html += "<div id='time-{{VOLID}}' class='time-div' data-volume-id='{{VOLID}}' style='display:none'>"
            html += "<div class='control-heading'>"
            html += "<span>Time:</span>"
            html += "</div>"
            html += "<input class='control-inputs' value='0' id='time-val-{{VOLID}}'/>"
            html += "<input type='checkbox' class='button' id='play-{{VOLID}}'><label for='play-{{VOLID}}'>Play</label>"
            html += "<div class='slider volume-viewer-threshold' id='time-slider-{{VOLID}}'></div>"
            html += "</div>"
            html += "</div>"
        else:
            html += "</div>"

        # Define a tool to change the colormap
        html += "<div class='control-container'>"
        html += "<div id='color-map-{{VOLID}}'>"
        html += "<div class='control-heading'>"
        html += "<span id='color-map-heading-{{VOLID}}'>"
        html += "Color Map:"
        html += "</span>"
        html += "</div>"
        html += "</div>"

        # Define a tool to display the selected voxel intensity
        html += "<div id='intensity-value-div-{{VOLID}}'>"
        html += "<div class='control-heading'>"
        html += "<span data-volume-id='{{VOLID}}'>"
        html += "Value:"
        html += "</span>"
        html += "</div>"
        html += ("<span id='intensity-value-{{VOLID}}' "
                 "class='intensity-value'></span>")
        html += "</div>"
        html += "</div>"

        # Define a tool to threshold the image
        html += "<div class='control-container'>"
        html += "<div class='threshold-div' data-volume-id='{{VOLID}}'>"
        html += "<div class='control-heading'>"
        html += "Brightness/Contrast:"
        html += "</div>"
        html += "<div class='thresh-inputs'>"
        html += ("<input id='min-threshold-{{VOLID}}' "
                 "class='control-inputs thresh-input-left' value='0'/>")
        html += ("<input id='max-threshold-{{VOLID}}' "
                 "class='control-inputs thresh-input-right' value='65535'/>")
        html += "</div>"
        html += ("<div class='slider volume-viewer-threshold' "
                 "id='threshold-slider-{{VOLID}}'></div>")
        html += "</div>"

        # Define a complete slicer tool
        html += ("<div id='slice-series-{{VOLID}}' "
                 "class='slice-series-div' data-volume-id='{{VOLID}}'>")
        html += ("<div class='control-heading' "
                 "id='slice-series-heading-{{VOLID}}'>All slices: </div>")
        html += ("<span class='slice-series-button button' "
                 "data-axis='xspace'>Sagittal</span>")
        html += ("<span class='slice-series-button button' "
                 "data-axis='yspace'>Coronal</span>")
        html += ("<span class='slice-series-button button' "
                 "data-axis='zspace'>Transverse</span>")
        html += "</div>"
        html += "</div>"

        # Define a tool to control the image contrast
        if contrast:
            html += "<div class='control-container'>"
            html += "<div class='contrast-div' data-volume-id='{{VOLID}}'>"
            html += ("<span class='control-heading' "
                     "id='contrast-heading{{VOLID}}'>Contrast (0.0 to 2.0):"
                     "</span>")
            html += ("<input class='control-inputs' value='1.0' "
                     "id='contrast-val'/>")
            html += ("<div id='contrast-slider' "
                     "class='slider volume-viewer-contrast'></div>")
            html += "</div>"
            html += "</div>"

        # Define a tool to control the image brightness
        if brightness:
            html += "<div class='control-container'>"
            html += "<div class='brightness-div' data-volume-id='{{VOLID}}'>"
            html += ("<span class='control-heading' "
                     "id='brightness-heading{{VOLID}}'>Brightness (-1 to 1):"
                     "</span>")
            html += "<input class='control-inputs' value='0' id='brightness-val'/>"
            html += ("<div id='brightness-slider' "
                     "class='slider volume-viewer-brightness'></div>")
            html += "</div>"
            html += "</div>"

        # End controls
        html += "</div>"

        # End javascript
        html += "</script>"

        return html

    def build_brainbrowser_banner(self, imagefiles):
        """ Define the default BrainBrowser banner.

        Parameters
        ----------
        imagefiles: list of str (mandatory)
            the path to the paths that will be rendered.

        Returns
        -------
        html: str
            the banner definition.
        """
        # Define a banner divs
        html = "<div id='brainbrowser-wrapper' style='display:none'>"
        html += "<div id='volume-viewer'>"
        html += "<div id='global-controls' class='volume-viewer-controls'>"

        # Define item to select the image rendering
        html += "<span class='control-heading'>Select rendering:</span>"
        html += "<select id='volume-rendering'>"
        html += "<option value='single'>Single</option>"
        html += "<option value='multi'>Multi</option>"
        html += "</select>"

        # Define item to select the image to be displayed
        html += "<select id='volume-type'>"
        for cnt, path in enumerate(imagefiles):
            html += "<option value='{0}'>{1}</option>".format(
                cnt, os.path.basename(path))
        html += "</select>"

        # Define item to change the panle size
        html += "<select id='volume-quality'>"
        html += "<option value='RAW' SELECTED>RAW</option>"
        # html += "<option value='LOW JPEG' SELECTED>LOW JPEG</option>"
        html += "</select>"

        # Define item to change the panel size
        html += "<span class='control-heading'>Panel size:</span>"
        html += "<select id='panel-size'>"
        html += "<option value='128'>128</option>"
        html += "<option value='256' SELECTED>256</option>"
        html += "<option value='512'>512</option>"
        html += "</select>"

        # Define item to reset displayed views
        # html += "<span id='sync-volumes-wrapper'>"
        # html += ("<input type='checkbox' class='button' id='reset-volumes'>"
        #          "<label for='reset-volumes'>Reset</label>")
        # html += "</span>"

        # Define item to create a screenshot
        html += "<span id='screenshot' class='button'>Screenshot</span>"
        html += ("<div class='instructions'>Shift-click to drag. Hold ctrl "
                 "to measure distance.</div>")

        # End divs
        html += "</div>"
        html += "<div id='brainbrowser'></div>"
        html += "</div>"
        html += "</div>"

        return html


@ajaxfunc(output_type="json")
def get_encoded_brainbrowser_image(self):
    """ Get image information and encoded buffer: formated for BrainBrowser.

    Returns
    -------
    im_info: dict
        the image information and encoded buffer.
    """
    # Get post parameters
    imagefile = self._cw.form["imagefile"]
    dquality = int(self._cw.form["dquality"])
    dtype = "JPEG"

    # Load the image
    im = nibabel.load(imagefile)
    header = im.header
    data = im.get_data()

    # Change the dynamic of the image intensities
    data = numpy.cast[numpy.uint8](
        (data - data.min()) * 255. / (data.max() - data.min()))

    # Build header and encode images
    dim = header["dim"]
    order = ["time", "xspace", "yspace", "zspace"]
    encoded_data = []
    if dim[0] == 3:

        # Build header
        header = {
            "order": order[1:],
            "xspace": {
                "start": float(header["qoffset_x"]),
                "space_length": int(dim[1]),
                "step": float(header["pixdim"][1]),
                "direction_cosines": [float(x) for x in header["srow_x"][:3]]},
            "yspace": {
                "start": float(header["qoffset_y"]),
                "space_length": int(dim[2]),
                "step": float(header["pixdim"][2]),
                "direction_cosines": [float(x) for x in header["srow_y"][:3]]},
            "zspace": {
                "start": float(header["qoffset_z"]),
                "space_length": int(dim[3]),
                "step": float(header["pixdim"][3]),
                "direction_cosines": [float(x) for x in header["srow_z"][:3]]},
        }

        # Encode the slice image data
        for index in range(data.shape[0]):
            slicedata = data[index]
            openfile = StringIO.StringIO()
            img = PIL.Image.fromarray(slicedata)
            img.save(openfile, format=dtype, quality=dquality)
            contents = openfile.getvalue()
            openfile.close()
            encoded_data.append(base64.b64encode(contents))

    elif dim[0] == 4:

        # Build header
        header = {
            "order": order,
            "xspace": {
                "start": float(header["qoffset_x"]),
                "space_length": int(dim[1]),
                "step": float(header["pixdim"][1]),
                "direction_cosines": [float(x) for x in header["srow_x"][:3]]},
            "yspace": {
                "start": float(header["qoffset_y"]),
                "space_length": int(dim[2]),
                "step": float(header["pixdim"][2]),
                "direction_cosines": [float(x) for x in header["srow_y"][:3]]},
            "zspace": {
                "start": float(header["qoffset_z"]),
                "space_length": int(dim[3]),
                "step": float(header["pixdim"][3]),
                "direction_cosines": [float(x) for x in header["srow_z"][:3]]},
            "time": {
                "start": 0,
                "space_length": int(dim[4])}
        }

        # Encode the slice image data
        data = numpy.transpose(data, (3, 0, 1, 2))
        for timepoint in range(data.shape[0]):
            for index in range(data.shape[1]):
                slicedata = data[timepoint, index]
                openfile = StringIO.StringIO()
                img = PIL.Image.fromarray(slicedata)
                img.save(openfile, format=dtype)
                contents = openfile.getvalue()
                openfile.close()
                encoded_data.append(base64.b64encode(contents))
    else:
        raise Exception("Only 3D or 3D + t images are currently supported!")

    # Format the output
    im_info = {
        "header": json.dumps(header),
        "data": encoded_data
    }

    return im_info


@ajaxfunc(output_type="json")
def get_brainbrowser_image(self):
    """ Get image information and buffer: formated for BrainBrowser.

    Returns
    -------
    im_info: dict
        the image information and buffer.
    """
    # Get post parameters
    imagefile = self._cw.form["imagefile"]

    # Load the image
    im = nibabel.load(imagefile)
    header = im.header
    try:
        data = im.get_data()
    # Missing bytes intern specific error that can be overcome with
    # an old lib
    except:
        import nifti
        im = nifti.NiftiImage(imagefile)
        data = im.getDataArray().T

    # Change the dynamic of the image intensities
    data = numpy.cast[numpy.uint16](
        (data - data.min()) * 65535. / (data.max() - data.min()))

    # Format the output
    dim = header["dim"]
    order = ["time", "xspace", "yspace", "zspace"]
    if dim[0] == 3:
        header = {
            "order": order[1:],
            "xspace": {
                "start": float(header["qoffset_x"]),
                "space_length": int(dim[1]),
                "step": float(header["pixdim"][1]),
                "direction_cosines": [float(x) for x in header["srow_x"][:3]]},
            "yspace": {
                "start": float(header["qoffset_y"]),
                "space_length": int(dim[2]),
                "step": float(header["pixdim"][2]),
                "direction_cosines": [float(x) for x in header["srow_y"][:3]]},
            "zspace": {
                "start": float(header["qoffset_z"]),
                "space_length": int(dim[3]),
                "step": float(header["pixdim"][3]),
                "direction_cosines": [float(x) for x in header["srow_z"][:3]]},
        }
    elif dim[0] == 4:
        header = {
            "order": order,
            "xspace": {
                "start": float(header["qoffset_x"]),
                "space_length": int(dim[1]),
                "step": float(header["pixdim"][1]),
                "direction_cosines": [float(x) for x in header["srow_x"][:3]]},
            "yspace": {
                "start": float(header["qoffset_y"]),
                "space_length": int(dim[2]),
                "step": float(header["pixdim"][2]),
                "direction_cosines": [float(x) for x in header["srow_y"][:3]]},
            "zspace": {
                "start": float(header["qoffset_z"]),
                "space_length": int(dim[3]),
                "step": float(header["pixdim"][3]),
                "direction_cosines": [float(x) for x in header["srow_z"][:3]]},
            "time": {
                "start": 0,
                "space_length": int(dim[4])}
        }
        data = numpy.transpose(data, (3, 0, 1, 2))
    else:
        raise Exception("Only 3D or 3D + t images are currently supported!")

    # Format the output
    im_info = {
        "header": json.dumps(header),
        "data": data.flatten().tolist()
    }

    return im_info
