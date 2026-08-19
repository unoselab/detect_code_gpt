def hwc_mixed_005_01(self):
        """use the base class to setup the source and destinations but add to
        that setup the instantiation of the "new_crash_source" """
        super(FetchTransformSaveWithSeparateNewCrashSourceApp, self) \
            ._setup_source_and_destination()
        if self.config.new_crash_source.new_crash_source_class:
            self.new_crash_source = \
                self.config.new_crash_source.new_crash_source_class(
                    self.config.new_crash_source,
                    name=self.app_instance_name,
                    quit_check_callback=self.quit_check
                )
        else:
            # the configuration failed to provide a "new_crash_source", fall
            # back to tying the "new_crash_source" to the "source".
            self.new_crash_source = self.source 

def agc_mixed_005_02(bam, samtype="bam"):
    """Check if bam file is valid.

    Bam file should:
    - exists
    - has an index (create if necessary)
    - is sorted by coordinate
    - has at least one mapped read
    """
    import os
    import pysam

    if not os.path.exists(bam):
        raise FileNotFoundError(f"File {bam} does not exist")

    with pysam.AlignmentFile(bam, "rb") as samfile:
        if not samfile.is_sorted():
            raise ValueError("BAM file is not sorted by coordinate")

        if not samfile.has_index():
            pysam.index(bam)

        has_mapped = False
        for read in samfile:
            if not read.is_unmapped:
                has_mapped = True
                break

        if not has_mapped:
            raise ValueError("BAM file has no mapped reads")

    return True 

def hwc_mixed_005_03(self,):
    """ Reset the state of all cells.
    This is normally used between sequences while training. All internal states
    are reset to 0.
    """

    self.activeState['t-1'].fill(0)
    self.activeState['t'].fill(0)
    self.predictedState['t-1'].fill(0)
    self.predictedState['t'].fill(0)
    self.learnState['t-1'].fill(0)
    self.learnState['t'].fill(0)
    self.confidence['t-1'].fill(0)
    self.confidence['t'].fill(0)

    # Flush the segment update queue
    self.segmentUpdates = {}

    self._internalStats['nInfersSinceReset'] = 0

    #To be removed
    self._internalStats['curPredictionScore'] = 0
    #New prediction score
    self._internalStats['curPredictionScore2']   = 0
    self._internalStats['curFalseNegativeScore'] = 0
    self._internalStats['curFalsePositiveScore'] = 0

    self._internalStats['curMissing'] = 0
    self._internalStats['curExtra'] = 0


    # When a reset occurs, set prevSequenceSignature to the signature of the
    # just-completed sequence and start accumulating histogram for the next
    # sequence.
    self._internalStats['prevSequenceSignature'] = None
    if self.collectSequenceStats:
      if self._internalStats['confHistogram'].sum() > 0:
        sig = self._internalStats['confHistogram'].copy()
        sig.reshape(self.numberOfCols * self.cellsPerColumn)
        self._internalStats['prevSequenceSignature'] = sig
      self._internalStats['confHistogram'].fill(0)

    self.resetCalled = True 

def agc_mixed_005_04(archive, compression, cmd, verbosity, interactive, filenames):
    """Create a CPIO archive."""
    import subprocess

    cmd_list = ['cpio']
    if compression:
        cmd_list.append('-c')
    if verbosity:
        cmd_list.append('-v')
    if interactive:
        cmd_list.append('-i')

    cmd_list.extend(['-o', '-H', 'newc'])

    with open(archive, 'wb') as f:
        process = subprocess.Popen(
            cmd_list,
            stdin=subprocess.PIPE,
            stdout=f,
            stderr=subprocess.PIPE,
            text=True
        )
        input_data = '\n'.join(filenames) + '\n'
        stdout, stderr = process.communicate(input=input_data)

        if process.returncode != 0:
            raise RuntimeError(f"CPIO failed: {stderr}") 

def agc_mixed_005_05(
    config,
    name,
    bucket,
    timeout,
    memory,
    description,
    subnet_ids,
    security_group_ids
):
    """ Deploy/Update a function from a project directory """
    # options should override config if it is there
    import boto3
    client = boto3.client('lambda', region_name=config.get('region', 'us-east-1'))

    with open(f"{config['project_dir']}/{config['zip_file']}", 'rb') as f:
        zip_content = f.read()

    params = {
        'FunctionName': name,
        'Runtime': config['runtime'],
        'Role': config['role_arn'],
        'Handler': config['handler'],
        'Code': {'ZipFile': zip_content},
        'Description': description,
        'Timeout': timeout,
        'MemorySize': memory,
        'VpcConfig': {
            'SubnetIds': subnet_ids,
            'SecurityGroupIds': security_group_ids
        }
    }

    try:
        client.get_function(FunctionName=name)
        return client.update_function_code(FunctionName=name, ZipFile=zip_content)
    except client.exceptions.ResourceNotFoundException:
        return client.create_function(**params) 

def hwc_mixed_005_06():
    """Interactively demonstrate the :mod:`coloredlogs` package."""
    # Determine the available logging levels and order them by numeric value.
    decorated_levels = []
    defined_levels = coloredlogs.find_defined_levels()
    normalizer = coloredlogs.NameNormalizer()
    for name, level in defined_levels.items():
        if name != 'NOTSET':
            item = (level, normalizer.normalize_name(name))
            if item not in decorated_levels:
                decorated_levels.append(item)
    ordered_levels = sorted(decorated_levels)
    # Initialize colored output to the terminal, default to the most
    # verbose logging level but enable the user the customize it.
    coloredlogs.install(level=os.environ.get('COLOREDLOGS_LOG_LEVEL', ordered_levels[0][1]))
    # Print some examples with different timestamps.
    for level, name in ordered_levels:
        log_method = getattr(logger, name, None)
        if log_method:
            log_method("message with level %s (%i)", name, level)
            time.sleep(DEMO_DELAY)
