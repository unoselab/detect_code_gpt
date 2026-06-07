def hwc_mixed_004_01(self):
        """
        Return a list of (prop, (form, valu)) refs out for the node.
        """
        retn = []

        for name, valu in self.props.items():

            pobj = self.form.props.get(name)

            if isinstance(pobj.type, s_types.Ndef):
                retn.append((name, valu))
                continue

            if self.snap.model.forms.get(pobj.type.name) is None:
                continue

            ndef = (pobj.type.name, valu)
            if ndef == self.ndef:
                continue

            retn.append((name, ndef))

        return retn 

def agc_mixed_004_02(self, show_text=True, show_moms=True):
        """Plots the lr rate/momentum schedule"""
        if not hasattr(self, 'lr_rates'):
            print("Plot lr schedule must be called after get_moms")
            return
        iterations = list(range(len(self.lr_rates)))
        if show_text:
            print(f"Min lr: {self.lr_min:.6f}")
            print(f"Max lr: {self.lr_max:.6f}")
            print(f"Min mom: {self.mom_min:.6f}")
            print(f"Max mom: {self.mom_max:.6f}")
        plt.plot(iterations, self.lr_rates, label='LR')
        if show_moms:
            plt.plot(iterations, self.mom_rates, label='MOM')
        plt.legend()
        plt.xlabel("Iterations")
        plt.ylabel("Rate")
        plt.show() 

def agc_mixed_004_03(self, serializers,
                                             default_media_type):
        """Match serializer by `Accept` headers."""
        # Bail out fast if no accept headers were given.
        if not serializers:
            return None

        accept_headers = self.request.META.get('HTTP_ACCEPT', '')
        accept_headers = [media_type.strip() for media_type in
                          accept_headers.split(',')]

        for media_type in accept_headers:
            if media_type == '*/*':
                return serializers[0]

            for serializer in serializers:
                if media_type == serializer.media_type:
                    return serializer

        return serializers[0] 

def agc_mixed_004_04(self, key, key_extra_len=0):
        """Checks sanity of key.  Fails if:
            Key length is > SERVER_MAX_KEY_LENGTH (Raises MemcachedKeyLength).
            Contains control characters  (Raises MemcachedKeyCharacterError).
            Is not a string (Raises MemcachedStringEncodingError)
            Is an unicode string (Raises MemcachedStringEncodingError)
            Is not a string (Raises MemcachedKeyError)
            Is None (Raises MemcachedKeyError)
        """
        if key is None:
            raise MemcachedKeyError("Key cannot be None")
        if not isinstance(key, basestring):
            raise MemcachedKeyError("Key must be a string")
        if isinstance(key, unicode):
            raise MemcachedStringEncodingError("Key must be a string")
        if len(key) > self.SERVER_MAX_KEY_LENGTH:
            raise MemcachedKeyLength("Key length is too long")
        if key_extra_len > 0:
            if len(key) + key_extra_len > self.SERVER_MAX_KEY_LENGTH:
                raise MemcachedKeyLength("Key length is too long")
        if not self.key_char_re.match(key):
            raise MemcachedKeyCharacterError("Key contains control characters") 

def hwc_mixed_004_05(cls, msg):
    """Try to log an error message to this process's error log and the shared error log.

    NB: Doesn't raise (logs an error instead).
    """
    pid = os.getpid()
    fatal_error_log_entry = cls._format_exception_message(msg, pid)

    # We care more about this log than the shared log, so write to it first.
    try:
      cls._try_write_with_flush(cls._pid_specific_error_fileobj, fatal_error_log_entry)
    except Exception as e:
      logger.error(
        "Error logging the message '{}' to the pid-specific file handle for {} at pid {}:\n{}"
        .format(msg, cls._log_dir, pid, e))

    # Write to the shared log.
    try:
      # TODO: we should probably guard this against concurrent modification by other pants
      # subprocesses somehow.
      cls._try_write_with_flush(cls._shared_error_fileobj, fatal_error_log_entry)
    except Exception as e:
      logger.error(
        "Error logging the message '{}' to the shared file handle for {} at pid {}:\n{}"
        .format(msg, cls._log_dir, pid, e)) 

def hwc_mixed_004_06(self):
        """
        Return a list of sound streams in this timeline and its children.
        The streams are returned in order with respect to the timeline.

        A stream is returned as a list: the first element is the tag
        which introduced that stream; other elements are the tags
        which made up the stream body (if any).
        """
        rc = []
        current_stream = None
        # looking in all containers for frames
        for tag in self.all_tags_of_type((TagSoundStreamHead, TagSoundStreamBlock)):
            if isinstance(tag, TagSoundStreamHead):
                # we have a new stream
                current_stream = [ tag ]
                rc.append(current_stream)
            if isinstance(tag, TagSoundStreamBlock):
                # we have a frame for the current stream
                current_stream.append(tag)
        return rc
