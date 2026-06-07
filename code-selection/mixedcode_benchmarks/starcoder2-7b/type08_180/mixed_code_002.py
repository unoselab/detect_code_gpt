def agc_mixed_002_01(self, issue, id=None, expand=None):
        """Get a list of the transitions available on the specified issue to the current user.

        :param issue: ID or key of the issue to get the transitions from
        :param id: if present, get only the transition matching this ID
        :param expand: extra information to fetch inside each transition
        """
        return self._get(
            self._expand_url(
                self._build_url(
                    'issue',
                    issue,
                    'transitions',
                    id=id,
                    expand=expand,
                ),
            ),
        ) 

def hwc_mixed_002_02(self, result):
        """Fix indentation undistinguish from the next logical line."""
        num_indent_spaces = int(result['info'].split()[1])
        line_index = result['line'] - 1
        target = self.source[line_index]

        spaces_to_add = num_indent_spaces - len(_get_indentation(target))
        indent = len(_get_indentation(target))
        modified_lines = []

        while len(_get_indentation(self.source[line_index])) >= indent:
            self.source[line_index] = (' ' * spaces_to_add +
                                       self.source[line_index])
            modified_lines.append(1 + line_index)  # Line indexed at 1.
            line_index -= 1

        return modified_lines 

def hwc_mixed_002_03():
    """ List the names of all cameras supported by libgphoto2, grouped by the
    name of their driver.
    """
    ctx = lib.gp_context_new()
    abilities_list_p = new_gp_object("CameraAbilitiesList")
    lib.gp_abilities_list_load(abilities_list_p, ctx)
    abilities = ffi.new("CameraAbilities*")
    out = []
    for idx in range(lib.gp_abilities_list_count(abilities_list_p)):
        lib.gp_abilities_list_get_abilities(abilities_list_p, idx, abilities)
        if abilities.device_type == lib.GP_DEVICE_STILL_CAMERA:
            libname = os.path.basename(ffi.string(abilities.library)
                                       .decode())
            out.append((ffi.string(abilities.model).decode(), libname))
    lib.gp_abilities_list_free(abilities_list_p)
    key_func = lambda name, driver: driver
    out = sorted(out, key=key_func)
    return {k: tuple(x[0] for x in v)
            for k, v in itertools.groupby(out, key_func)}
    return out 

def agc_mixed_002_04(path, files, **kwargs):
    """ Make a well layout in chunks of two from a list of files

    path: str
        Location to make the well html file
    files: list of pycbc.workflow.core.Files
        This list of images to show in order within the well layout html file.
        Every two are placed on the same row.
    """
    html_file = open(path, 'w')
    html_file.write(html_header)
    html_file.write(html_body_start)

    # Make the rows
    for i in range(0, len(files), 2):
        html_file.write(html_row_start)
        for j in range(2):
            if i + j < len(files):
                html_file.write(html_col_start)
                html_file.write(html_img_start)
                html_file.write(html_img_src % files[i + j].path)
                html_file.write(html_img_end)
                html_file.write(html_col_end)
        html_file.write(html_row_end)

    html_file.write(html_body_end)
    html_file.write(html_footer)
    html_file.close() 

def agc_mixed_002_05(self, only_status=False, show_cluster=True):
        """
        Print infos on this node configuration.
        """
        print("Node %s" % self.name)
        print("  - IP: %s" % self.ip)
        print("  - Status: %s" % self.status)
        print("  - Cluster: %s" % self.cluster)
        if not only_status:
            print("  - Services:")
            for service in self.services:
                print("    - %s" % service)
        if show_cluster:
            print("  - Cluster:")
            for node in self.cluster:
                print("    - %s" % node) 

def hwc_mixed_002_06(path, pattern='', verbose=False):
    """Opener that opens files from tar archive.

    :param str path: Path.
    :param str pattern: Regular expression pattern.
    :return: Filehandle(s).
    """
    with tarfile.open(fileobj=io.BytesIO(urlopen(path).read())) if is_url(path) else tarfile.open(path) as tararchive:
        for tarinfo in tararchive:
            if tarinfo.isfile():
                source = os.path.join(path, tarinfo.name)

                if pattern and not re.match(pattern, tarinfo.name):
                    logger.verbose('Skipping file: {}, did not match regex pattern "{}"'.format(os.path.abspath(tarinfo.name), pattern))
                    continue

                logger.verbose('Processing file: {}'.format(source))
                filehandle = tararchive.extractfile(tarinfo)
                yield filehandle
