# PanoSynthVR
PanoSynthVR: View Synthesis From A Single Input Panorama with Multi-Cylinder Images

# Conda environment

To create and activate the conda environment:

    conda env create
    conda activate panosynthvr

Then run download_mpi.sh to get the MPI code and pre-trained weights.


Run MCI generation only
```
  python generate_mci.py --input example.jpg --width 2048 --height 1024 --o outputfolder
```
Run MCI generation only and display output in website using WebXR
```
  python generate_mci.py --input example.jpg --width 2048 --height 1024 --o outputfolder --s 1
```

Run MCI generation on a video (folder of png images) and convert to a webm video 
```
  python generate_mci.py --input inputfolder --width 2048 --height 1024 --o outputfolder --videoOutput True

    ffmpeg -y -r 60 -i %05d.png -c:v prores_ks -profile:v 4 -pix_fmt yuva444p10le tmp.mov

    ffmpeg -i tmp.mov -vf unpremultiply=inplace=1 -c:v libvpx-vp9 -b:v 0 -crf 31 myMPIVideoName.webm

```
