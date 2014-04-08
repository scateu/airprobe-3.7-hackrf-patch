[Source](http://www.rtl-sdr.com/rtl-sdr-tutorial-analyzing-gsm-with-airprobe-and-wireshark/)

The new version 3.7 GNU Radio is not compatible with AirProbe.
You will need to install GNU Radio 3.6.
However, neeo from the comments section of this post has created a [patch](http://speedy.sh/9rYp7/zmiana.patch) which makes AirProbe compatible with GNU Radio 3.7.



## Install libosmocore
        git clone git://git.osmocom.org/libosmocore.git
        cd libosmocore
        autoreconf –i
        ./configure
        make
        sudo make install
        sudo ldconfig

## Install airprobe
Only patch airprobe/gsm-receiver

    $ cd airprobe
    $ patch -p1 < ~/hackrf/01Book/files/GSM/zmiana.patch

      patching file gsm-receiver/Makefile.common
      patching file gsm-receiver/config/gr_libgnuradio_core_extra_ldflags.m4
      patching file gsm-receiver/config/gr_standalone.m4
      patching file gsm-receiver/src/lib/Makefile.swig.gen
      patching file gsm-receiver/src/lib/gsm.i
      patching file gsm-receiver/src/lib/gsm_constants.h
      patching file gsm-receiver/src/lib/gsm_receiver_cf.cc
      patching file gsm-receiver/src/lib/gsm_receiver_cf.h
      patching file gsm-receiver/src/python/gsm_receive.py

    $ . ./bootstrap

