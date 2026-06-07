def hwc_mixed_002_01(self):
        """
        Returns the localized name of the document (see l10n)
        """
        if self.is_new:
            return _("New document")
        try:
            split = self.__docid.split("_")
            short_docid = "_".join(split[:3])
            datetime_obj = datetime.datetime.strptime(
                short_docid, self.DOCNAME_FORMAT)
            final = datetime_obj.strftime("%x")
            return final
        except Exception as exc:
            logger.error("Unable to parse document id [%s]: %s"
                         % (self.docid, exc))
            return self.docid 

def agc_mixed_002_02(self, scaling_group, name, cooldown, min_entities,
            max_entities, metadata=None):
        """
        Replace an existing ScalingGroup configuration. All of the attributes
        must be specified If you wish to delete any of the optional attributes,
        pass them in as None.
        """
        if metadata is None:
            metadata = {}
        return self.connection.request(
            'ReplaceScalingGroup',
            params={
                'ScalingGroupName': scaling_group,
                'MinSize': min_entities,
                'MaxSize': max_entities,
                'Cooldown': cooldown,
                'Metadata': metadata,
                'Name': name,
            },
        ) 

def agc_mixed_002_03(cls, stream, marker_code, offset):
        """
        Return an |_App0Marker| instance for the APP0 marker at *offset* in
        *stream*.
        """
        # field               off  type   notes
        # ------------------  ---  -----  -------------------
        # segment length       0   short
        # JFIF identifier      2   5 chr  'JFIF\x00'
        # major JPEG version   7   byte   typically 1
        # minor JPEG version   8   byte   typically 1 or 2
        # density units        9   byte   1=inches, 2=cm
        # horz dots per unit  10   short
        # vert dots per unit  12   short
        # ------------------  ---  -----  -------------------
        stream.seek(offset)
        if stream.read(2)!= marker_code:
            raise ValueError("Invalid APP0 marker")
        length = stream.read_uint16()
        if length < 14:
            raise ValueError("Invalid APP0 marker")
        length -= 14
        version = stream.read(4)
        if version!= b"JFIF\0":
            raise ValueError("Invalid APP0 marker")
        units = stream.read_uint16()
        xdensity = stream.read_uint16()
        ydensity = stream.read_uint16()
        thumb_width = stream.read_uint8()
        thumb_height = stream.read_uint8()
        thumb_data = stream.read(thumb_width * thumb_height)
        return cls(version, units, xdensity, ydensity, thumb_data) 

def hwc_mixed_002_04(self, name, args, mkdir=True):
        """Get a named filesystem entry, and extend it into a path with additional
        path arguments"""
        from os.path import normpath
        from ambry.dbexceptions import ConfigurationError

        root = p = self._config.filesystem[name].format(root=self._root)

        if args:
            args = [e.strip() for e in args]
            p = join(p, *args)

        if not isdir(p) and mkdir:
            makedirs(p)

        p = normpath(p)

        if not p.startswith(root):
            raise ConfigurationError("Path for name='{}', args={} resolved outside of define filesystem root"
                                 .format(name, args))

        return p 

def agc_mixed_002_05(items, config):
    """Identify problem batch setups for somatic calling.

    We do not support multiple tumors in a single batch and VarDict(Java) does not
    handle pooled calling, only tumor/normal.
    """
    if len(items) > 1:
        raise ValueError(
            "Multiple tumors in a single batch is not supported by VarDictJava."
        )

    if len(items) == 1:
        if items[0].tumor_id!= items[0].normal_id:
            raise ValueError(
                "VarDictJava does not support pooled calling, only tumor/normal."
            )

    if len(items) == 1 and items[0].tumor_id == items[0].normal_id:
        if items[0].tumor_id == items[0].normal_id:
            raise ValueError(
                "VarDictJava does not support pooled calling, only tumor/normal."
            ) 

def hwc_mixed_002_06(self):
        """Returns main data set from self

        Returns:
            X (numpy.ndarray): Features

            y (numpy.ndarray): Labels
        """
        if not self.main_dataset['source']:
            raise exceptions.UserError('Source is empty')

        extraction_code = self.main_dataset["source"]

        extraction_function = functions.import_object_from_string_code(extraction_code,
                                                                       "extract_main_dataset")
        try:
            X, y = extraction_function()
        except Exception as e:
            raise exceptions.UserError('User code exception', exception_message=str(e))

        X, y = np.array(X), np.array(y)

        return X, y
