def hwc_mixed_004_01(self, filepath, fprogress):
        """Store file at filepath in the database and return the base index entry
        Needs the git_working_dir decorator active ! This must be assured in the calling code"""
        st = os.lstat(filepath)     # handles non-symlinks as well
        if S_ISLNK(st.st_mode):
            # in PY3, readlink is string, but we need bytes. In PY2, it's just OS encoded bytes, we assume UTF-8
            open_stream = lambda: BytesIO(force_bytes(os.readlink(filepath), encoding=defenc))
        else:
            open_stream = lambda: open(filepath, 'rb')
        with open_stream() as stream:
            fprogress(filepath, False, filepath)
            istream = self.repo.odb.store(IStream(Blob.type, st.st_size, stream))
            fprogress(filepath, True, filepath)
        return BaseIndexEntry((stat_mode_to_index_mode(st.st_mode),
                               istream.binsha, 0, to_native_path_linux(filepath))) 

def agc_mixed_004_02(self, bucket, label, keys):
        """Delete the metadata corresponding to the specified keys.
        """
        if not self.is_connected():
            raise RuntimeError('Not connected to the database.')

        if not self.is_bucket_exists(bucket):
            raise RuntimeError('Bucket %s does not exist.' % bucket)

        if not self.is_label_exists(bucket, label):
            raise RuntimeError('Label %s does not exist.' % label)

        if not isinstance(keys, list):
            raise TypeError('keys must be a list.')

        if len(keys) == 0:
            raise ValueError('keys must not be empty.')

        for key in keys:
            if not isinstance(key, str):
                raise TypeError('key must be a string.')

        self.db.delete_metadata_keys(bucket, label, keys) 

def agc_mixed_004_03(self, element_cls, prop_name):
        """
        Add the appropriate methods to *element_cls*.
        """
        if prop_name == 'class_members':
            element_cls.add_class_member = self.add_class_member
            element_cls.remove_class_member = self.remove_class_member
            element_cls.get_class_member = self.get_class_member
            element_cls.get_class_members = self.get_class_members
            element_cls.get_class_members_by_name = self.get_class_members_by_name
            element_cls.get_class_members_by_type = self.get_class_members_by_type
            element_cls.get_class_members_by_name_and_type = self.get_class_members_by_name_and_type
            element_cls.get_class_members_by_name_and_type_and_value = self.get_class_members_by_name_and_type_and_value
            element_cls.get_class_members_by_name_and_type_and_value_and_key = self.get_class_members_by_name_and_type_and_value_and_key
            element_cls.get_class_members_by_name_and_type_and_value_and_key_and_value = self.get_class_members_by_name_and_type_and_value_and_key_and_value
            element_cls.get_class_members_by_name_and_type_and_value_and_key_and_value_and_key = self.get_class_members_by_name_and_type_and_value_and_key_and_value_and_key
            element_cls.get_class_members_by_name_and_type_and_value_and_key_and_value_and_key_and_value = self.get_class_members_by_name_and_type_and_value_and_key_and_value_and_key_and_value
            element_cls.get_class_members_by_name_and_type_and_value_and_key_and_value_and_key_and_value_and_ 

def hwc_mixed_004_04(self, uri, disable_proxy=False, stream=False):
        """Return Requests response to GET request."""
        response = requests.get(
            uri,
            headers=self.headers,
            allow_redirects=True,
            cookies={},
            stream=stream,
            proxies=self.proxy if not disable_proxy else False
        )

        if response.status_code in _PERMITTED_STATUS_CODES:
            self.response_headers = response.headers
            return response.content if not stream else response.iter_content()
        else:
            raise requests.exceptions.HTTPError(
                "HTTP response did not have a permitted status code."
            ) 

def agc_mixed_004_05(self, progress, prefix=''):
        """
        Print a progress bar for longer-running scripts.

        The progress value is a value between 0.0 and 1.0. If a prefix is
        present, it will be printed before the progress bar.
        """
        bar_length = 20
        if isinstance(progress, int):
            progress = float(progress)
        if not isinstance(progress, float):
            progress = 0
        if progress < 0:
            progress = 0
        if progress >= 1:
            progress = 1

        block = int(round(bar_length * progress))

        if prefix:
            print(prefix, end='')

        print("\r[{0}] {1:.1f}%".format(
            "#" * block + "-" * (bar_length - block), progress * 100), end='')

        if progress >= 1:
            print() 

def hwc_mixed_004_06(self, minimum_solid_angle):
        """
        Remove regions of magnitude-magnitude space where the unmasked solid angle is
        statistically insufficient to estimate the background.

        INPUTS:
            solid_angle[1]: minimum solid angle (deg^2)
        """

        logger.info('Pruning mask based on minimum solid angle of %.2f deg^2'%(minimum_solid_angle))

        solid_angle_mmd = self.solid_angle_mmd*(self.solid_angle_mmd > minimum_solid_angle)
        if solid_angle_mmd.sum() == 0:
            msg = "Pruned mask contains no solid angle."
            logger.error(msg)
            raise Exception(msg)

        self.solid_angle_mmd = solid_angle_mmd

        # Compute which magnitudes the clipping correspond to
        index_mag_1, index_mag_2 = np.nonzero(self.solid_angle_mmd)
        self.mag_1_clip = self.roi.bins_mag[1:][np.max(index_mag_1)]
        self.mag_2_clip = self.roi.bins_mag[1:][np.max(index_mag_2)]

        logger.info('Clipping mask 1 at %.2f mag'%(self.mag_1_clip) )
        logger.info('Clipping mask 2 at %.2f mag'%(self.mag_2_clip) )
        self.mask_1.mask_roi_sparse = np.clip(self.mask_1.mask_roi_sparse, 0., self.mag_1_clip)
        self.mask_2.mask_roi_sparse = np.clip(self.mask_2.mask_roi_sparse, 0., self.mag_2_clip)
