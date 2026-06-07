def agc_mixed_001_01(vm_name, vm_config_spec, folder_object, resourcepool_object, host_object=None):
    """
    Creates virtual machine from config spec

    vm_name
        Virtual machine name to be created

    vm_config_spec
        Virtual Machine Config Spec object

    folder_object
        vm Folder managed object reference

    resourcepool_object
        Resource pool object where the machine will be created

    host_object
        Host object where the machine will ne placed (optional)

    return
        Virtual Machine managed object reference
    """
    vm_object = None
    try:
        vm_object = folder_object.vmFolder.CreateVM_Task(vm_name, vm_config_spec, resourcepool_object)
        if host_object is not None:
            vm_object.RelocateVM_Task(host_object)
        vm_object.WaitForTask(task=vm_object.task, max_wait_seconds=300)
        if vm_object.task.info.state =='success':
            return vm_object
        else:
            raise Exception("Failed to create VM: %s" % vm_object.task.info.error)
    except Exception as e:
        raise Exception("Failed to create VM: %s" % e)
    finally:
        if vm_object is not None:
            vm_object.Destroy() 

def hwc_mixed_001_02(obj):
    """
    Returns all the coordinate tuples from a geometry or feature.

    """
    if isinstance(obj, (tuple, list)):
        coords = obj
    elif 'features' in obj:
        coords = [geom['geometry']['coordinates'] for geom in obj['features']]
    elif 'geometry' in obj:
        coords = obj['geometry']['coordinates']
    else:
        coords = obj.get('coordinates', obj)
    for coord in coords:
        if isinstance(coord, (float, int)):
            yield tuple(coords)
            break
        else:
            for f in iter_coords(coord):
                yield f 

def agc_mixed_001_03(area):
    """Return the cf grid mapping for the geos projection."""
    return {
        "grid_mapping_name": "geos",
        "longitude_of_prime_meridian": 0.0,
        "semi_major_axis": 6378137.0,
        "inverse_flattening": 298.257223563,
        "latitude_of_projection_origin": 0.0,
        "false_easting": 0.0,
        "false_northing": 0.0,
        "longitude_of_central_meridian": 0.0,
        "sweep_angle_axis": "x",
        "standard_parallel": 0.0,
        "scale_factor_at_projection_origin": 1.0,
        "scale_factor_at_central_meridian": 1.0,
        "north_pole_latitude": 90.0,
        "north_pole_longitude": 0.0,
        "earth_shape": "sphere",
        "area": area,
    } 

def agc_mixed_001_04(cls, o, base_uri):
        """Returns a new ``Link`` based on a JSON object or array.

        Arguments:

        - ``o``: a dictionary holding the deserializated JSON for the new
                 ``Link``, or a ``list`` of such documents.
        - ``base_uri``: optional URL used as the basis when expanding
                               relative URLs in the link.

        """
        if isinstance(o, list):
            return [cls.from_object(i, base_uri) for i in o]
        if not isinstance(o, dict):
            raise ValueError("Invalid JSON object")
        return cls(o.get('href', None), o.get('rel', None),
                   o.get('title', None), o.get('type', None),
                   o.get('hreflang', None), o.get('media', None),
                   o.get('profile', None), o.get('length', None),
                   base_uri) 

def hwc_mixed_001_05(self, cnts):
        """Write summary of level and depth counts for active GO Terms."""
        # Count level(shortest path to root) and depth(longest path to root)
        # values for all unique GO Terms.
        max_val = max(max(dep for dep in cnts['depth']),
                      max(lev for lev in cnts['level']))
        self.log.write('Dep <-Depth Counts->  <-Level Counts->\n')
        self.log.write('Lev   BP    MF    CC    BP    MF    CC\n')
        self.log.write('--- ----  ----  ----  ----  ----  ----\n')
        for i in range(max_val+1):
            vals = ['{:>5}'.format(cnts[desc][i][ns]) for desc in sorted(cnts) for ns in self.nss]
            self.log.write('{:>02} {}\n'.format(i, ' '.join(vals))) 

def hwc_mixed_001_06(song):
    """
    Returns the lyrics found in lyricsmode.com for the specified mp3 file or an
    empty string if not found.
    """
    translate = {
        URLESCAPE: '',
        ' ': '_'
    }
    artist = song.artist.lower()
    artist = normalize(artist, translate)
    title = song.title.lower()
    title = normalize(title, translate)

    artist = re.sub(r'\_{2,}', '_', artist)
    title = re.sub(r'\_{2,}', '_', title)

    if artist[0:4].lower() == 'the ':
        artist = artist[4:]

    if artist[0:2].lower() == 'a ':
        prefix = artist[2]
    else:
        prefix = artist[0]

    url = 'http://www.lyricsmode.com/lyrics/{}/{}/{}.html'
    url = url.format(prefix, artist, title)
    soup = get_url(url)
    content = soup.find(id='lyrics_text')

    return content.get_text().strip()
