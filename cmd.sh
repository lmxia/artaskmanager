apt-get install libglu1

./python/bin/python3.9 -m pip install  numpy==1.23.5
/python/bin/python3.9 -m pip install opencv-contrib-python-headless==4.4.0.46
./python/bin/python3.9 -m pip install  esdk-obs-python


nohup ./metashape -r artaskmanager/main.py -platform offscreen >> 3dbuild.log  2>&1 &