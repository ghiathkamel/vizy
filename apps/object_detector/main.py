#
# This file is part of Vizy 
#
# All Vizy source code is provided under the terms of the
# GNU General Public License v2 (http://www.gnu.org/licenses/gpl-2.0.html).
# Those wishing to use Vizy source code, software and/or
# technologies under different licensing terms should contact us at
# support@charmedlabs.com. 
#

import os
import cv2
import time
import json
import datetime
import numpy as np
from threading import Thread
import kritter
from kritter import get_color
from kritter.tflite import TFliteDetector
from dash_devices.dependencies import Output
import dash_html_components as html
from vizy import Vizy
from handle_event import handle_event
from kritter.ktextvisor import KtextVisor, KtextVisorTable

MIN_THRESHOLD = 0.1
MAX_THRESHOLD = 0.9
THRESHOLD_HYSTERESIS = 0.2

CONFIG_FILE = "object_detector.json"
DEFAULT_CONFIG = {
    "brightness": 50,
    "detection_threshold": 50,
    "enabled_classes": None,
    "trigger_classes": []
}
BASEDIR = os.path.dirname(__file__)
MEDIA_DIR = os.path.join(BASEDIR, "media")
IMAGES_KEEP = 10
IMAGES_DISPLAY = 5

class DetectionPicker:
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.info = {}

    def _value(self, det, image):
        # If score0 is in det, it means the the current frame has object in it.  
        # We only want to consider pictures with detected object in it, not
        # pictures where object has disappeared (for example).
        if 'score0' in det:
            box = det['box']
            area = (box[2]-box[0])*(box[3]-box[1])
            # Crop object out of image
            box = image[box[1]:box[3], box[0]:box[2], :]
            # Calculate sharpness of image by calculating edges on green channel
            # and averaging.
            c = cv2.Canny(box[:, :, 1], 50, 250)
            sharpness = np.mean(c)
            return area*sharpness
        else:
            return 0

    def update(self, image, dets):
        t = time.time()
        for k, v in dets.items():
            try:
                if self.info[k][3]==0:
                    continue
            except:
                pass
            v['box'] = v['box'][0:4].tolist() # make list, get rid of extra bits
            value = self._value(v, image)
            try:
                # Update class to most recent because it's the most accurate.
                self.info[k][1]['class'] = v['class']
                # If value exceeds current max, set info.
                if value>self.info[k][0]:
                    self.info[k][0:3] = [value, v, image]
            except:
                self.info[k] = [value, v, image, t]

        # Determine which object(s) we deregistered, if any.
        deregs = set(self.info.keys())-set(dets.keys())

        # Determine which objects have timed-out, if any.
        timeouts = []
        for k, v in self.info.items():
            if v[3]!=0 and t-v[3]>self.timeout and k not in deregs:
                v[3] = 0
                timeouts.append(k)

        res = []
        # Go through deregistered objects, add to result, but only if it wasn't a timeout
        for i in deregs:
            if self.info[i][3]!=0: # If i isn't a timeout
                res.append((self.info[i][2], self.info[i][1]))
            del self.info[i]
        # Go through timeouts, add to result
        for i in timeouts:
            res.append((self.info[i][2], self.info[i][1]))

        return res

class ObjectDetector:
    def __init__(self):

        # Create Kritter server.
        self.kapp = Vizy()
        self.kapp.media_path.insert(0, MEDIA_DIR)

        config_filename = os.path.join(self.kapp.etcdir, CONFIG_FILE)      
        self.config = kritter.ConfigFile(config_filename, DEFAULT_CONFIG)               

        # Create and start camera.
        self.camera = kritter.Camera(hflip=True, vflip=True)
        self.stream = self.camera.stream()
        self.camera.mode = "768x432x10bpp"
        self.camera.brightness = self.config['brightness']
        self.camera.framerate = 30
        self.camera.autoshutter = True
        self.camera.awb = True

        # Invoke KtextVisor client, which relies on the server running.
        # In case it isn't running, we just roll with it.  
        try:
            self.tv = KtextVisor()
            print("*** Texting interface found!")
        except:
            self.tv = None
            print("*** Texting interface not found.")

        self.store_media = kritter.SaveMediaQueue(path=MEDIA_DIR, keep=IMAGES_KEEP)
        self.tracker = kritter.DetectionTracker()
        self.picker = DetectionPicker()
        self.detector_process = kritter.Processify(TFliteDetector, (None, ))
        self.detector = kritter.KimageDetectorThread(self.detector_process)
        if self.config['enabled_classes'] is None:
            self.config['enabled_classes'] = self.detector_process.classes()
        self.set_threshold(self.config['detection_threshold']/100)

        style = {"label_width": 3, "control_width": 6}

        # Create video component and histogram enable.
        self.video = kritter.Kvideo(width=self.camera.resolution[0], overlay=True)
        brightness = kritter.Kslider(name="Brightness", value=self.camera.brightness, mxs=(0, 100, 1), format=lambda val: f'{val}%', style=style)
        self.images_div = html.Div(id=self.kapp.new_id(), style={"white-space": "nowrap", "max-width": "768px", "width": "100%", "overflow-x": "auto"})
        threshold = kritter.Kslider(name="Detection threshold", value=self.config['detection_threshold'], mxs=(MIN_THRESHOLD*100, MAX_THRESHOLD*100, 1), format=lambda val: f'{int(val)}%', style=style)
        enabled_classes = kritter.Kchecklist(name="Enabled classes", options=self.detector_process.classes(), value=self.config['enabled_classes'], clear_check_all=True, scrollable=True)
        trigger_classes = kritter.Kchecklist(name="Trigger classes", options=self.config['enabled_classes'], value=self.config['trigger_classes'], clear_check_all=True, scrollable=True)

        @brightness.callback()
        def func(value):
            self.config['brightness'] = value
            self.camera.brightness = value
            self.config.save()

        @threshold.callback()
        def func(value):
            self.config['detection_threshold'] = value
            self.set_threshold(value/100) 
            self.config.save()

        @enabled_classes.callback()
        def func(value):
            self.config['enabled_classes'] = value
            self.config.save()

        @trigger_classes.callback()
        def func(value):
            self.config['trigger_classes'] = value
            self.config.save()

        controls = html.Div([brightness, threshold, enabled_classes, trigger_classes])
        # Add video component and controls to layout.
        self.kapp.layout = html.Div([html.Div([self.video, self.images_div]), controls], style={"padding": "15px"})
        self.kapp.push_mods(self.out_images())
        # Run camera grab thread.
        self.run_thread = True
        self._grab_thread = Thread(target=self.grab_thread)
        self._grab_thread.start()

        # Run Kritter server, which blocks.
        self.kapp.run()
        self.run_thread = False
        self._grab_thread.join()
        self.detector.close()
        self.detector_process.close()
        self.store_media.close()

    def set_threshold(self, threshold):
        self.tracker.setThreshold(threshold)
        self.low_threshold = threshold - THRESHOLD_HYSTERESIS
        if self.low_threshold<MIN_THRESHOLD:
            self.low_threshold = MIN_THRESHOLD 

    # Frame grabbing thread
    def grab_thread(self):
        while self.run_thread:
            # Get frame
            frame = self.stream.frame()[0]
            # Get raw detections from detector thread
            detect = self.detector.detect(frame, self.low_threshold)
            if detect is not None:
                dets, det_frame = detect
                print("**** dets", len(dets))
                # Remove classes that aren't active
                dets = self._filter_dets(dets)
                # Feed detections into tracker
                dets = self.tracker.update(dets, showDisappeared=True)
                # Render tracked detections to overlay
                mods = kritter.render_detected(self.video.overlay, dets)
                # Update picker
                mods += self.handle_picks(det_frame, dets)
                self.kapp.push_mods(mods)

            # Send frame
            self.video.push_frame(frame)

    def handle_picks(self, frame, dets):
        picks = self.picker.update(frame, dets)
        if picks:
            for i in picks:
                image, data = i[0], i[1]
                # Save picture and metadata, add width and height of image to data so we don't
                # need to decode it to set overlay dimensions.
                timestamp = datetime.datetime.now().strftime("%a %H:%M:%S")
                self.store_media.store_image_array(image, data={**data, 'width': image.shape[1], 'height': image.shape[0], "timestamp": timestamp})
                if data['class'] in self.config['trigger_classes']:
                    event = {**data, 'image': image, 'event_type': 'trigger', "timestamp": timestamp}
                    handle_event(self, event)

            return self.out_images()
        return []       

    def _filter_dets(self, dets):
        dets = [det for det in dets if det['class'] in self.config['enabled_classes']]
        return dets

    def out_images(self):
        images = os.listdir(MEDIA_DIR)
        images = [i for i in images if i.endswith(".jpg")]
        images.sort(reverse=True)
        images = images[0:IMAGES_DISPLAY]
        children = []
        for i in images:
            basename = kritter.file_basename(i)
            with open(os.path.join(MEDIA_DIR, basename+'.json')) as file:
                data = json.load(file)
            kimage = kritter.Kimage(width=300, src=i, overlay=True, style={"display": "inline-block", "margin": "5px 5px 5px 0"})
            kimage.overlay.update_resolution(width=data['width'], height=data['height'])
            kritter.render_detected(kimage.overlay, [data])
            kimage.overlay.draw_text(0, data['height']-1, data['timestamp'], fillcolor="black", font=dict(family="sans-serif", size=12, color="white"), xanchor="left", yanchor="bottom")
            children.append(kimage.layout)
        return [Output(self.images_div.id, "children", children)]

if __name__ == "__main__":
    ObjectDetector()
