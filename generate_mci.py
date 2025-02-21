import numpy as np
import os
import subprocess
import tensorflow as tf
from single_view_mpi.libs import mpi
from single_view_mpi.libs import nets
import cv2
from cv2 import imwrite
import glob
from zipfile import ZipFile
import sys
import time
import threading
import webbrowser
import shutil
from http.server import HTTPServer, SimpleHTTPRequestHandler



def loadWebsite(foldername, imagename):
    """ Copy images over to asset folder and display it in a website using WebXR"""
    imagename = os.path.basename(imagename).split('.')[0]

    print (foldername)
    print (imagename)

    ip = "127.0.0.1"
    port = 3600
    #folder = "outputc"
    folder = foldername
    #imagename = "bicyle"
    srcfolder =folder+'/'+imagename

    webfiles = "docs/assets"
    dest = webfiles + '/'+ imagename
    destDirAbs = os.path.abspath(dest)
    #input_path
    #args.output
    url = f"http://{ip}:{port}/docs/renderer.html?mode=mpi&scene=-1&name=" + imagename

    src_files = os.listdir(srcfolder)

    if not os.path.exists(destDirAbs):
        os.makedirs(destDirAbs)
        print ('Created:'+ destDirAbs)
    for file_name in src_files:
        full_file_name = os.path.join(srcfolder, file_name)
        if os.path.isfile(full_file_name):

            full_outfile_name = os.path.join(destDirAbs, file_name)
            print("copying ... " + full_outfile_name)
            shutil.copy(full_file_name, full_outfile_name)


    def start_server():
        server_address = (ip, port)
        httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
        httpd.serve_forever()


    threading.Thread(target=start_server).start()
    webbrowser.open_new(url)

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)



def load_model():
    """ Build MPI model and load pre-trained weights."""
    inputs = tf.keras.Input(shape=(None, None, 3))
    output = nets.mpi_from_image(inputs)

    model = tf.keras.Model(inputs=inputs, outputs=output)
    model.load_weights('single_view_mpi_full_keras/single_view_mpi_keras_weights')

    return model

def generate(model, input_path, output_path, output_width, output_height, build_atlas=True, videoOutput=False):
    """ Generate multi-cylinder images from input images.
        Arguments:
            - model: MPI Keras model
            - input_path: path to input image or directory of input images (PNG)
            - output_path: path to output directory
            - output_width: output image size (will resize input)
            - output_height: output image size (will resize input)
            - build_atlas: build texture atlas rather than storing individual layer images
    """
    # Get depths of MCI layers
    depths = mpi.make_depths(1.0, 100.0, 32).numpy()

    print("process: " + input_path)
    # Get paths to images
    if os.path.isdir(input_path):
        paths = sorted(glob.glob(os.path.join(args.input,'*.png')))
    else:
        paths = [input_path]

    for path in paths:
        print(path)

        # Load image
        input_rgb = tf.image.decode_image(tf.io.read_file(path), dtype=tf.float32)

        # Resize if necessary
        input_rgb = tf.image.resize(input_rgb, (output_height,output_width), method='area')

        # Cylindrical wrap padding
        height, width = input_rgb.shape[:2]
        padding = width//4
        left = input_rgb[:, 0:padding]
        right = input_rgb[:, width-padding:width]
        input_rgb_padded = np.concatenate((right, input_rgb, left), axis=1)

        # Generate MCI layers
        layers_padded = model(input_rgb_padded[tf.newaxis])[0] # (L, H, W, 4)

        # Remove padding
        layers = layers_padded[:,:,padding:-padding,:]

        # Get disparity from layers
        disparity = mpi.disparity_from_layers(layers, depths)
        disparity = tf.squeeze(disparity)

        # Make output directory
        my_output_path = os.path.join(output_path,os.path.basename(path).split('.')[0])
        os.makedirs(my_output_path,exist_ok=True)

        # Save input image
        input_bgr = cv2.cvtColor((input_rgb.numpy()*255).astype('uint8'),cv2.COLOR_RGB2BGR)
        imwrite(f'{my_output_path}/input.png',input_bgr)

        # Save disparity map
        imwrite(f'{my_output_path}/disparity_map.png',
               (disparity*255).numpy().astype('uint8'))

        def get_layer(layers,n):
            layer = layers[n].numpy()
            layer[:,:,:3] *= layer[:,:,3:] # pre-multiply alpha
            layer = (layer*255).astype('uint8')
            layer = cv2.cvtColor(layer,cv2.COLOR_RGBA2BGRA)
            return layer

        if not build_atlas:
            # Output individual layer images
            os.makedirs(f'{my_output_path}/layers',exist_ok=True)
            for n in range(32):
                layer = get_layer(layers,n)
                imwrite(f'{my_output_path}/layers/layer_{n}.png', layer)
        else:
            # Build atlas
            H,W = output_height,output_width
            rows = 8
            cols = 4
            atlas = np.zeros((H*rows,W*cols,4),dtype='uint8')
            n = 0
            for r in range(rows):
                myr = (rows-1)-r
                for c in range(cols):
                    layer = get_layer(layers,n)
                    atlas[H*myr:H*(myr+1),W*c:W*(c+1)] = layer[:,::-1] # flip horizontally for rendering on backside of cylinder
                    n = n + 1
            imwrite(os.path.join(my_output_path,'atlas.png'),atlas)

        if videoOutput:
            #os.makedirs(os.path.dirname(dest_fpath), exist_ok=True)
            filename = os.path.join(my_output_path,'atlas.png')
            purefileName = os.path.basename(path).split('/')[0]
            filenameNew = os.path.join(output_path, purefileName)
            print (filename + ", " + filenameNew)
            shutil.copyfile(filename, filenameNew)
            #subprocess.call(['ffmpeg', '-y', '-r', '30', '-i', 'bike%06d.png','-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le', 'tmp.mov'])
            #subprocess.call('ffmpeg -i tmp.mov -vf unpremultiply=inplace=1 -c:v libvpx-vp9 -b:v 0 -crf 31 bike5.webm', shell=True)


if __name__ == '__main__':
    from argparse import ArgumentParser
    import glob
    import os

    parser = ArgumentParser(description='Generate multi-cylinder image from input panorama')

    parser.add_argument('--input',
                        required=True,
                        help='input image or directory')
    parser.add_argument('--width',
                        required=True,
                        type=int,
                        help='output image width (will resize)')
    parser.add_argument('--height',
                        required=True,
                        type=int,
                        help='output image height (will resize)')
    parser.add_argument('--output', '-o',
                        required=True,
                        help='output directory')
    parser.add_argument('--videoOutput', '-v', required=False, help='output a video from input')

    parser.add_argument('--showWeb', '-s', required=False, help='show website')

    args = parser.parse_args()

    # Create the output directory
    os.makedirs(args.output,exist_ok=True)

    # Load Keras model
    model = load_model()

    generate(model=model, input_path=args.input, output_path=args.output, build_atlas=True, output_width=args.width, output_height=args.height, videoOutput=args.videoOutput)

    #show website optional
    if args.showWeb == "1":
        loadWebsite(foldername=args.output, imagename=args.input)
