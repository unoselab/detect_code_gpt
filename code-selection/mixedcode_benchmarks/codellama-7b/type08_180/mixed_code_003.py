def hwc_mixed_003_01(content):
        """
        utility function to parse feed
        """
        feed = feedparser.parse(content)
        articles = []
        for entry in feed['entries']:
            article = {
                'title': entry['title'],
                'link': entry['link']
            }
            try:
                article['media'] = entry['media_content'][0]['url']
            except KeyError:
                article['media'] = None
            articles.append(article)
        return articles 

def agc_mixed_003_02(self, fieldspec):
        """
        Removes fields or subfields according to `fieldspec`.

        If a non-control field subfield removal leaves no other subfields,
        delete the field entirely.
        """

        fields = self.fields
        for field in fields:
            if field.tag in fieldspec:
                if field.tag in MARC21_CONTROL_FIELDS:
                    continue
                for subfield in field.subfields:
                    if subfield.code in fieldspec[field.tag]:
                        field.remove_subfield(subfield.code)
                if not field.subfields:
                    self.remove_field(field) 

def hwc_mixed_003_03(url, replace_existing=False, fix_wprogram=True):
    """install library from web or local files system.

    :param url: web address or file path
    :param replace_existing: bool
    :rtype: None

    """
    d = tmpdir(tmpdir())
    f = download(url)
    Archive(f).extractall(d)

    clean_dir(d)
    d, src_dlib = find_lib_dir(d)
    move_examples(d, src_dlib)
    fix_examples_dir(src_dlib)
    if fix_wprogram:
        fix_wprogram_in_files(src_dlib)

    targ_dlib = libraries_dir() / src_dlib.name
    if targ_dlib.exists():
        log.debug('library already exists: %s', targ_dlib)
        if replace_existing:
            log.debug('remove %s', targ_dlib)
            targ_dlib.rmtree()
        else:
            raise ConfduinoError('library already exists:' + targ_dlib)

    log.debug('move %s -> %s', src_dlib, targ_dlib)
    src_dlib.move(targ_dlib)

    libraries_dir().copymode(targ_dlib)
    for x in targ_dlib.walk():
        libraries_dir().copymode(x)
    return targ_dlib.name 

def agc_mixed_003_04(dstpath, srcpath, names=None, 
                                       languages=None):
    """ Update or add manifest XML from srcpath as resource in dstpath """
    if not names:
        names = ['manifest']
    if not languages:
        languages = ['en']
    for name in names:
        for language in languages:
            src = os.path.join(srcpath, name + '.xml')
            dst = os.path.join(dstpath, name + '_' + language + '.xml')
            if os.path.exists(src):
                if os.path.exists(dst):
                    UpdateManifestResourceFromXMLFile(dst, src)
                else:
                    CopyFile(src, dst) 

def agc_mixed_003_05(self, filepath, format='png', quality=90):
        """Used for generating thumbnails.  Does not include overlaid
        graphics.
        """
        if format == 'png':
            self.figure.savefig(filepath, format=format, dpi=self.dpi,
                                transparent=True, bbox_inches='tight',
                                pad_inches=0, quality=quality)
        else:
            self.figure.savefig(filepath, format=format, dpi=self.dpi,
                                transparent=True, bbox_inches='tight',
                                pad_inches=0) 

def hwc_mixed_003_06(self):
        """
        Adds a new continuous set into this repo
        """
        self._openRepo()
        dataset = self._repo.getDatasetByName(self._args.datasetName)
        filePath = self._getFilePath(self._args.filePath,
                                     self._args.relativePath)
        name = getNameFromPath(self._args.filePath)
        continuousSet = continuous.FileContinuousSet(dataset, name)
        referenceSetName = self._args.referenceSetName
        if referenceSetName is None:
            raise exceptions.RepoManagerException(
                "A reference set name must be provided")
        referenceSet = self._repo.getReferenceSetByName(referenceSetName)
        continuousSet.setReferenceSet(referenceSet)
        continuousSet.populateFromFile(filePath)
        self._updateRepo(self._repo.insertContinuousSet, continuousSet)
