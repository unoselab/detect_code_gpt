def hwc_mixed_001_01(self, name, default_value=None):
        """Retrieve a value from DB"""
        value = self.spine.send_query("retrieveSetting", self.group, name, processes=["kervi-main"])
        if value is None:
            return default_value
        elif isinstance(value, list) and len(value) == 0:
            return default_value
        elif isinstance(default_value, int):
            return int(value)
        elif isinstance(default_value, float):
            return float(value)
        else:
            return value 

def agc_mixed_001_02(self, level, correlation_id, ex, message):
        """
        Writes a log message to the logger destination.

        :param level: a log level.

        :param correlation_id: (optional) transaction id to trace execution through call chain.

        :param ex: an error object associated with this message.

        :param message: a human-readable message to log.
        """
        if level == "ERROR":
            self.logger.error(f"ERROR: {correlation_id} - {ex} - {message}")
        elif level == "WARNING":
            self.logger.warning(f"WARNING: {correlation_id} - {ex} - {message}")
        elif level == "INFO":
            self.logger.info(f"INFO: {correlation_id} - {ex} - {message}")
        elif level == "DEBUG":
            self.logger.debug(f"DEBUG: {correlation_id} - {ex} - {message}")
        else:
            raise ValueError("Invalid log level") 

def agc_mixed_001_03(self, conversion: _Text = 'badgerfish') -> Mapping:
        """A JSON Representation of the XML.  Default is badgerfish.
        :param conversion: Which conversion method to use. (`learn more <https://github.com/sanand0/xmljson#conventions>`_)
        """
        if conversion == 'badgerfish':
            json_dict = {}
            for child in self:
                if child.tag not in json_dict:
                    json_dict[child.tag] = []
                json_dict[child.tag].append(child.json(conversion))
            return json_dict
        else:
            raise ValueError(f"Invalid conversion method: {conversion}") 

def agc_mixed_001_04(I, shape, size):
    """
    Get flattened indices for the border of the region I.

    Parameters
    ----------
    I : np.ndarray(dtype=int)
        indices in the flattened region.
    size : int
        region size (technically computable from shape argument)
    shape : tuple(int, int)
        region shape

    Returns
    -------
    J : np.ndarray(dtype=int)
        indices orthogonally and diagonally bordering I
    """

    J = []
    for i in I:
        row, col = np.unravel_index(i, shape)
        for r in range(max(0, row - 1), min(shape[0], row + 2)):
            for c in range(max(0, col - 1), min(shape[1], col + 2)):
                j = np.ravel_multi_index((r, c), shape)
                if j not in I and j not in J:
                    J.append(j)

    return np.array(J) 

def hwc_mixed_001_05(request, exclude_section=False):
    """
    Returns trail of breadcrumbs (vertical cut, excluding base level)
    """
    trail = []
    url = request.path
    while url:
        if url == '/':
            break
        if exclude_section and url in SECTIONS:
            break
        crumb = find_crumb(request, url)
        if not crumb:
            break
        trail.append(crumb)

        # go one level up
        url = urljoin(url, '..')

    trail.reverse()

    return trail 

def hwc_mixed_001_06(in_file, data, max_distance=10000, work_dir=None):
    """Add gene annotations to a BED file from pre-prepared RNA-seq data.

    max_distance -- only keep annotations within this distance of event
    """
    gene_file = regions.get_sv_bed(data, "exons", out_dir=os.path.dirname(in_file))
    if gene_file and utils.file_exists(in_file):
        out_file = "%s-annotated.bed" % utils.splitext_plus(in_file)[0]
        if work_dir:
            out_file = os.path.join(work_dir, os.path.basename(out_file))
        if not utils.file_uptodate(out_file, in_file):
            fai_file = ref.fasta_idx(dd.get_ref_file(data))
            with file_transaction(data, out_file) as tx_out_file:
                _add_genes_to_bed(in_file, gene_file, fai_file, tx_out_file, data, max_distance)
        return out_file
    else:
        return in_file
