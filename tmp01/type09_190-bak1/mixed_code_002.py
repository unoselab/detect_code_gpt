def agc_mixed_002_01(self, seqprop, structprop, chain_id,
                                      seq_ident_cutoff=0.5, allow_missing_on_termini=0.2,
                                      allow_mutants=True, allow_deletions=False,
                                      allow_insertions=False, allow_unresolved=True):
        """Report if a structure's chain meets the defined cutoffs for sequence quality."""
        seq_ident = seqprop.get_sequence_identity(structprop, chain_id)
        if seq_ident < seq_ident_cutoff:
            return False
        missing_residues = seqprop.get_missing_residues(structprop, chain_id)
        if missing_residues > allow_missing_on_termini:
            return False
        if not allow_mutants and seqprop.has_mutants(structprop, chain_id):
            return False
        if not allow_deletions and seqprop.has_deletions(structprop, chain_id):
            return False
        if not allow_insertions and seqprop.has_insertions(structprop, chain_id):
            return False
        if not allow_unresolved and seqprop.has_unresolved(structprop, chain_id):
            return False
        return True 

def hwc_mixed_002_02(self, env, target_name='control',
                     file_name='control.json',
                     encoder_cls=SConsEncoder):
        """
        Adds a target to build a control file at each of the current leaves.

        :param env: SCons Environment object
        :param target_name: Name for target in nest
        :param file_name: Name for output file.
        """
        if not HAS_SCONS:
            raise ImportError('SCons not available')

        @self.add_target(name=target_name)
        def control(outdir, c):
            return env.Command(os.path.join(outdir, file_name),
                               [],
                               action=_create_control_file,
                               control_dict=c,
                               encoder_cls=encoder_cls) 

def agc_mixed_002_03(self, bbox):
    """See base class for details."""
    # Validate the coordinates
    if not isinstance(bbox, np.ndarray):
        raise TypeError("bbox must be a numpy array")
    if bbox.shape!= (4,):
        raise ValueError("bbox must be a 1D array of length 4")
    if not np.issubdtype(bbox.dtype, np.floating):
        raise ValueError("bbox must be a floating-point array")
    if not np.all(np.isfinite(bbox)):
        raise ValueError("bbox must contain only finite values")
    if not np.all(bbox >= 0):
        raise ValueError("bbox must contain only non-negative values")
    if not np.all(bbox <= 1):
        raise ValueError("bbox must contain values in the range [0, 1]")
    encoded_example = np.zeros(self.encoded_example_size, dtype=np.float32)
    encoded_example[0] = bbox[0] * self.encoded_example_size
    encoded_example[1] = bbox[1] * self.encoded_example_size
    encoded_example[2] = np.log(bbox[2] / bbox[0]) * self.encoded_example_size
    encoded_example[3] = np.log(bbox[3] / bbox[1]) * self.encoded_example_size

    return encoded_example 

def hwc_mixed_002_04():
    """
    Shortcut for instantiating and returning a boto SESConnection object.

    :rtype: boto.ses.SESConnection
    :returns: A boto SESConnection object, from which email sending is done.
    """

    access_key_id = getattr(
        settings, 'CUCUMBER_SES_ACCESS_KEY_ID',
        getattr(settings, 'AWS_ACCESS_KEY_ID', None))
    access_key = getattr(
        settings, 'CUCUMBER_SES_SECRET_ACCESS_KEY',
        getattr(settings, 'AWS_SECRET_ACCESS_KEY', None))
    region_name = getattr(
        settings, 'CUCUMBER_SES_REGION_NAME',
        getattr(settings, 'AWS_SES_REGION_NAME', None))

    if region_name != None:
        return boto.ses.connect_to_region(
            region_name,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=access_key,
        )
    else:
        return boto.connect_ses(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=access_key,
        ) 

def agc_mixed_002_05(
            self, environment: Environment, template: str,
    ) -> Tuple[str, Optional[str], Callable]:
        """Returns the template source from the environment.

        This considers the loaders on the :attr:`app` and blueprints.
        """
        for loader in self.app.template_loaders:
            if hasattr(loader, "get_source"):
                source, path, uid = loader.get_source(environment, template)
                if source is not None:
                    return source, path, uid

        for loader in self.app.template_loaders:
            if hasattr(loader, "get_source"):
                source, path, uid = loader.get_source(environment, template)
                if source is not None:
                    return source, path, uid

        raise TemplateNotFound(template) 

def hwc_mixed_002_06(config=None, name=None, name_label='name'):
        """
        Fetches a K8sDeployment by name.

        :param config: A K8sConfig object.
        :param name: The name we want.
        :param name_label: The label key to use for name.
        :return: A list of K8sDeployment objects.
        """

        if name is None:
            raise SyntaxError(
                'Deployment: name: [ {0} ] cannot be None.'.format(name))
        if not isinstance(name, str):
            raise SyntaxError(
                'Deployment: name: [ {0} ] must be a string.'.format(name))

        if config is not None and not isinstance(config, K8sConfig):
            raise SyntaxError(
                'Deployment: config: [ {0} ] must be a K8sConfig'.format(config))

        deps = K8sDeployment(config=config, name=name).list(labels={
            name_label: name
        })

        return deps
