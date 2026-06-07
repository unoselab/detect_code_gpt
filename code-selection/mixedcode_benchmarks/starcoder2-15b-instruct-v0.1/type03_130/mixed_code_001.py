def hwc_mixed_001_01(dest, source, env):
    """Install a versioned library into a destination by copying,
    (including copying permission/mode bits) and then creating
    required symlinks."""

    if os.path.isdir(source):
        raise SCons.Errors.UserError("cannot install directory `%s' as a version library" % str(source) )
    else:
        # remove the link if it is already there
        try:
            os.remove(dest)
        except:
            pass
        shutil.copy2(source, dest)
        st = os.stat(source)
        os.chmod(dest, stat.S_IMODE(st[stat.ST_MODE]) | stat.S_IWRITE)
        installShlibLinks(dest, source, env)

    return 0 

def agc_mixed_001_02(self, audio_file_mfcc):
        """
        Set the audio file head or tail,
        by either reading the explicit values
        from the Task configuration,
        or using SD to determine them.

        This function returns the lengths, in seconds,
        of the (head, process, tail).

        :rtype: tuple (float, float, float)
        """
        if self.head is not None:
            head = self.head
        else:
            head = self.sd.head

        if self.tail is not None:
            tail = self.tail
        else:
            tail = self.sd.tail

        process = len(audio_file_mfcc) - head - tail

        return head, process, tail 

def agc_mixed_001_03(self, cursor, subdomain_rec, history_neighbors):
        """
        Try to insert a subdomain record into its history neighbors.
        This is an optimization that handles the "usual" case.

        We can do this without having to rewrite this subdomain's past and future
        if (1) we can find a previously-accepted subdomain record, and (2) the transition 
        from this subdomain record to a future subdomain record preserves its
        acceptance as True.  In this case, the "far" past and "far" future are already
        consistent.

        Return True if we succeed in doing so.
        Return False if not.
        """
        if subdomain_rec.accepted is True:
            for neighbor in history_neighbors:
                if neighbor.accepted is True:
                    cursor.execute("INSERT INTO subdomain (subdomain_id, accepted, history_id) VALUES (?,?,?)",
                        (subdomain_rec.subdomain_id, subdomain_rec.accepted, subdomain_rec.history_id))
                    return True
        return False 

def hwc_mixed_001_04(this_class, stream):
        """Construct a Corpus. stream is an iterable over strings where
        each string is a line in CoNLL-X format."""
        stream = iter(stream)
        corpus = this_class()
        while 1:
            # read until we get an empty sentence
            sentence = Sentence.from_conll(stream)
            if sentence:
                corpus.append(sentence)
            else:
                break
        return corpus 

def agc_mixed_001_05(cls: Type[T], data: Generic) -> T:
        """Build objects from dictionaries, recursively."""
        if isinstance(data, dict):
            obj = cls()
            for key, value in data.items():
                setattr(obj, key, build(cls, value))
            return obj
        elif isinstance(data, list):
            return [build(cls, item) for item in data]
        else:
            return data 

def hwc_mixed_001_06(ir_blocks):
    """Assert that optional Traverse blocks are preceded by a MarkLocation."""
    # Once all fold blocks are removed, each optional Traverse must have
    # a MarkLocation block immediately before it.
    _, new_ir_blocks = extract_folds_from_ir_blocks(ir_blocks)
    for first_block, second_block in pairwise(new_ir_blocks):
        # Traverse blocks with optional=True are immediately preceded by a MarkLocation block.
        if isinstance(second_block, Traverse) and second_block.optional:
            if not isinstance(first_block, MarkLocation):
                raise AssertionError(u'Expected MarkLocation before Traverse with optional=True, '
                                     u'but none was found: {}'.format(ir_blocks))
