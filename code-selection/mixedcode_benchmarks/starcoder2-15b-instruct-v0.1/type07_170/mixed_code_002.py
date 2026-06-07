def hwc_mixed_002_01(query, configuration=None, **kwargs):
        # type: (str, Optional[Configuration], Any) -> List['Resource']
        """Searches for resources in HDX. NOTE: Does not search dataset metadata!

        Args:
            query (str): Query
            configuration (Optional[Configuration]): HDX configuration. Defaults to global configuration.
            **kwargs: See below
            order_by (str): A field on the Resource model that orders the results
            offset (int): Apply an offset to the query
            limit (int): Apply a limit to the query
        Returns:
            List[Resource]: List of resources resulting from query
        """

        resources = []
        resource = Resource(configuration=configuration)
        success, result = resource._read_from_hdx('resource', query, 'query', Resource.actions()['search'])
        if result:
            count = result.get('count', None)
            if count:
                for resourcedict in result['results']:
                    resource = Resource(resourcedict, configuration=configuration)
                    resources.append(resource)
        else:
            logger.debug(result)
        return resources 

def agc_mixed_002_02(activity_data, epoch_list):
    """ create data epoch by epoch

    Separate data into epochs of interest specified in epoch_list
    and z-score them for computing correlation

    Parameters
    ----------
    activity_data: list of 2D array in shape [nVoxels, nTRs]
        the masked activity data organized in voxel*TR formats of all subjects
    epoch_list: list of 3D array in shape [condition, nEpochs, nTRs]
        specification of epochs and conditions
        assuming all subjects have the same number of epochs
        len(epoch_list) equals the number of subjects

    Returns
    -------
    raw_data: list of 2D array in shape [epoch length, nVoxels]
        the data organized in epochs
        and z-scored in preparation of correlation computation
        len(raw_data) equals the number of epochs
    labels: list of 1D array
        the condition labels of the epochs
        len(labels) labels equals the number of epochs
    """
    raw_data = []
    labels = []
    for subject_data, subject_epochs in zip(activity_data, epoch_list):
        for condition, epochs in enumerate(subject_epochs):
            for epoch in epochs:
                epoch_data = subject_data[:, epoch]
                epoch_mean = np.mean(epoch_data, axis=1)
                epoch_std = np.std(epoch_data, axis=1)
                z_scored_epoch = (epoch_data - epoch_mean[:, np.newaxis]) / epoch_std[:, np.newaxis]
                raw_data.append(z_scored_epoch.T)
                labels.append(condition)

    return raw_data, labels 

def agc_mixed_002_03(
        seq,
        check_gen9_seqs=True,
        check_short_length=True,
        check_local_gc_content=True,
        check_global_gc_content=True):
    """
    Raise a ValueError if the given sequence doesn't pass all of the Gen9 
    quality control design guidelines.  Certain checks can be enabled or 
    disabled via the command line.
    """

    if check_gen9_seqs:
        if not seq.startswith('G9'):
            raise ValueError('Sequence does not start with "G9"')
    if check_short_length:
        if len(seq) < 100:
            raise ValueError('Sequence is too short')
    if check_local_gc_content:
        gc_count = seq.count('G') + seq.count('C')
        if gc_count < 0.3 * len(seq):
            raise ValueError('Sequence has low local GC content')
    if check_global_gc_content:
        gc_count = seq.count('G') + seq.count('C')
        if gc_count < 0.4 * len(seq):
            raise ValueError('Sequence has low global GC content') 

def agc_mixed_002_04(self, var_g):
        """**EXPERIMENTAL**

        converts a single hgvs allele to (chr, pos, ref, alt) using
        the given assembly_name. The chr name uses official chromosome
        name (i.e., without a "chr" prefix).

        Returns None for non-variation (e.g., NC_000006.12:g.49949407=)

        """

        if var_g.is_deletion():
            ref = var_g.ref_allele.seq
            alt = ""
        elif var_g.is_insertion():
            ref = ""
            alt = var_g.alt_allele.seq
        elif var_g.is_snv():
            ref = var_g.ref_allele.seq
            alt = var_g.alt_allele.seq
        else:
            return None
        pos = var_g.pos
        chr = var_g.ac
        return (chr, pos, ref, alt) 

def hwc_mixed_002_05(self,cutoff):
        """
        This function defines the residues for plotting in case only a topology file has been submitted.
        In this case the residence time analysis in not necessary and it is enough just to find all
        residues within a cutoff distance.
            Takes:
                * cutoff * - cutoff distance in angstroms that defines native contacts
            Output:
                *
        """

        #self.protein_selection = self.universe.select_atoms('all and around '+str(cutoff)+' (segid '+str(self.universe.ligand.segids[0])+' and resid '+str(self.universe.ligand.resids[0])+')')
        #The previous line was not working on some examples for some reason - switch to more efficient Neighbour Search
        n = AtomNeighborSearch(self.universe.select_atoms('protein and not name H* or (segid '+str(self.universe.ligand.segids[0])+' and resid '+str(self.universe.ligand.resids[0])+')'), bucket_size=10)
        self.protein_selection = n.search(self.universe.ligand,cutoff,level="A")
        for atom in self.protein_selection.atoms:
                #for non-analysis plots
                residue = (atom.resname, str(atom.resid), atom.segid)
                if residue not in self.dict_of_plotted_res.keys() and atom not in self.universe.ligand.atoms:
                    self.dict_of_plotted_res[residue]=[1]
        assert len(self.dict_of_plotted_res)!=0, "Nothing to draw for this ligand (residue number: "+ self.universe.ligand.resids[0] +" on the chain "+ self.universe.ligand.segids[0] +") - check the position of your ligand within the topology file." 

def hwc_mixed_002_06(self, name, config, cfg_section='default', remove_sasbase=False):
        """Generate the relevant Sphinx nodes.

        Generates a section for the Tree datamodel.  Formats a tree section
        as a list-table directive.

        Parameters:
            name (str):
                The name of the config to be documented, e.g. 'sdsswork'
            config (dict):
                The tree dictionary of the loaded config environ
            cfg_section (str):
                The section of the config to load
            remove_sasbase (bool):
                If True, removes the SAS_BASE_DIR from the beginning of each path

        Returns:
            A section docutil node

        """

        # the source name
        source_name = name

        # Title
        section = nodes.section(
            '',
            nodes.title(text=cfg_section),
            ids=[nodes.make_id(cfg_section)],
            names=[nodes.fully_normalize_name(cfg_section)])

        # Summarize
        result = statemachine.ViewList()
        base = config['default']['filesystem'] if remove_sasbase else None
        lines = _format_command(cfg_section, config[cfg_section], base=base)
        for line in lines:
            result.append(line, source_name)

        self.state.nested_parse(result, 0, section)

        return [section]
