def hwc_mixed_001_01(self, query, out_params):
        """Applies the filter by client to the search query
        """
        current_client = logged_in_client(self.context)
        if current_client:
            query['getClientUID'] = api.get_uid(current_client)
        elif self.request.form.get("ClientUID", ""):
            query['getClientUID'] = self.request.form['ClientUID']
            client = api.get_object_by_uid(query['getClientUID'])
            out_params.append({'title': _('Client'),
                               'value': client.Title(),
                               'type': 'text'}) 

def agc_mixed_001_02(link):
        """Convert a reddit URL into the short-hand used by usernotes.

        Arguments:
            link: a link to a comment, submission, or message (str)

        Returns a String of the shorthand URL
        """
        if link.startswith('http://www.reddit.com/'):
            link = link[20:]
        elif link.startswith('http://reddit.com/'):
            link = link[17:]
        elif link.startswith('http://'):
            link = link[7:]
        elif link.startswith('https://www.reddit.com/'):
            link = link[20:]
        elif link.startswith('https://reddit.com/'):
            link = link[17:]
        elif link.startswith('https://'):
            link = link[8:]
        return link 

def agc_mixed_001_03(self):
        """
        Get all date about the current execution frame

        :return: current frame data
        :rtype: dict
        :raises AttributeError: if the debugger does hold any execution frame.
        :raises IOError: if source code for the current execution frame is not accessible.
        """
        if not self.has_current_frame():
            raise AttributeError("No current frame")

        frame = self.current_frame()
        frame_data = {
            "file": frame.f_code.co_filename,
            "line": frame.f_lineno,
            "function": frame.f_code.co_name,
            "locals": frame.f_locals,
            "globals": frame.f_globals,
            "source": self.get_source_code(frame),
        }
        return frame_data 

def agc_mixed_001_04(self, tb_, **kwargs):
        """Get the radiance from the brightness temperature (Tb) given the
        band name.

        Input:
          tb_: Brightness temperature of the band (self.band)

        Optional arguments:
          lut: If not none, this is a Look Up Table with tb and radiance values
            which will be used for the conversion. Default is None.

          normalized: If True, the derived radiance values are the spectral radiances for the band.
            If False the radiance is the band integrated radiance. Default is True.

        """
        if self.lut is None:
            self.lut = self.get_lut()
        if self.lut is None:
            raise ValueError('No LUT available')
        if 'normalized' in kwargs:
            normalized = kwargs['normalized']
        else:
            normalized = True
        if normalized:
            return self.lut.get_radiance(tb_)
        else:
            return self.lut.get_band_integrated_radiance(tb_) 

def hwc_mixed_001_05(self):
        """Prints the include and library path being used for debugging purposes."""
        if self.static_extension:
            build_type = "static extension"
        else:
            build_type = "dynamic extension"
        print("Build type: %s" % build_type)
        print("Include path: %s" % " ".join(self.include_dirs))
        print("Library path: %s" % " ".join(self.library_dirs))
        print("Linked dynamic libraries: %s" % " ".join(self.libraries))
        print("Linked static libraries: %s" % " ".join(self.extra_objects))
        print("Extra compiler options: %s" % " ".join(self.extra_compile_args))
        print("Extra linker options: %s" % " ".join(self.extra_link_args)) 

def hwc_mixed_001_06(arr, crange, cmap, hex=True):
    """
    Maps an array of values to RGB hex strings, given
    a color range and colormap.
    """
    if isinstance(crange, np.ndarray):
        xsorted = np.argsort(crange)
        ypos = np.searchsorted(crange, arr)
        arr = xsorted[ypos]
    else:
        if isinstance(crange, tuple):
            cmin, cmax = crange
        else:
            cmin, cmax = np.nanmin(arr), np.nanmax(arr)
        arr = (arr - cmin) / (cmax-cmin)
        arr = np.ma.array(arr, mask=np.logical_not(np.isfinite(arr)))
    arr = cmap(arr)
    if hex:
        return rgb2hex(arr)
    else:
        return arr
