def hwc_mixed_004_01(schedule: Schedule) -> Iterable[Dict]:
    """Convert a schedule into an iterable of proto dictionaries.

    Args:
        schedule: The schedule to convert to a proto dict. Must contain only
            gates that can be cast to xmon gates.

    Yields:
        A proto dictionary corresponding to an Operation proto.
    """
    last_time_picos = None  # type: Optional[int]
    for so in schedule.scheduled_operations:
        op = gate_to_proto_dict(
            cast(ops.GateOperation, so.operation).gate,
            so.operation.qubits)
        time_picos = so.time.raw_picos()
        if last_time_picos is None:
            op['incremental_delay_picoseconds'] = time_picos
        else:
            op['incremental_delay_picoseconds'] = time_picos - last_time_picos
        last_time_picos = time_picos
        yield op 

def hwc_mixed_004_02(self, s):
        """
        Provided with the record header and AEAD-ciphered data, return the
        sliced and clear tuple (TLSInnerPlaintext, tag). Note that
        we still return the slicing of the original input in case of decryption
        failure. Also, if the integrity check fails, a warning will be issued,
        but we still return the sliced (unauthenticated) plaintext.
        """
        rcs = self.tls_session.rcs
        read_seq_num = struct.pack("!Q", rcs.seq_num)
        rcs.seq_num += 1
        try:
            return rcs.cipher.auth_decrypt(b"", s, read_seq_num)
        except CipherError as e:
            return e.args
        except AEADTagError as e:
            pkt_info = self.firstlayer().summary()
            log_runtime.info("TLS: record integrity check failed [%s]", pkt_info)  # noqa: E501
            return e.args 

def agc_mixed_004_03(self, data):
        """
        Add a single character to buffer. If one or more full lines are found,
        print them (if desired) and pass to callback function.
        """
        self.buffer = getattr(self, 'buffer', '') + data
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            line += '\n'
            if getattr(self, 'print', False):
                print(line, end='')
            cb = getattr(self, 'callback', None)
            if callable(cb):
                cb(line) 

def hwc_mixed_004_04(self, widget, index=0, row=None,
                  col=0, rowspan=1, colspan=1):
        """
        Add new widget inside dock, remove old one if existent
        """
        if row is None:
            row = self.currentRow
        self.currentRow = max(row + 1, self.currentRow)
        if index > len(self.widgets) - 1:
            # add new widget
            self.widgets.append(widget)
        else:  # change existing widget
            self.layout.removeWidget(self.widgets[index])
            self.widgets[index] = widget
        self.layout.addWidget(widget, row, col, rowspan, colspan)
        self.raiseOverlay() 

def agc_mixed_004_05(self, number):
        """Return name of book with given index."""
        if not isinstance(number, int):
            raise TypeError("number must be an integer")
        try:
            books = self.books
        except AttributeError as exc:
            raise AttributeError("Instance lacks a 'books' attribute") from exc
        try:
            return books[number]
        except Exception as exc:
            raise IndexError(f"Book index {number} is out of range") from exc 

def agc_mixed_004_06(self, state, storage_load=False):
        """Adds a state to the container state.

        :param state: the state that is going to be added
        :param storage_load: True if the state was directly loaded from filesystem
        :return: the state_id of the new state
        :raises exceptions.AttributeError: if state.state_id already exist
        """
        if not hasattr(self, "_states"):
            self._states = {}
        sid = getattr(state, "state_id", None)
        if sid is None:
            raise AttributeError("state must have a 'state_id' attribute")
        if sid in self._states:
            raise AttributeError(f"state_id {sid} already exists")
        self._states[sid] = state
        if storage_load and hasattr(state, "_loaded"):
            state._loaded = True
        return sid
