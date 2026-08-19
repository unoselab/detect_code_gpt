def agc_mixed_004_01(self, condition=None, page_size=1000):
        """Return an iterator over all monitors matching the provided condition

        Get all inactive monitors and print id::

            for mon in dc.monitor.get_monitors(MON_STATUS_ATTR == "DISABLED"):
                print(mon.get_id())

        Get all the HTTP monitors and print id::

            for mon in dc.monitor.get_monitors(MON_TRANSPORT_TYPE_ATTR == "http"):
                print(mon.get_id())

        Many other possibilities exist.  See the :mod:`devicecloud.condition` documention
        for additional details on building compound expressions.

        :param condition: An :class:`.Expression` which defines the condition
            which must be matched on the monitor that will be retrieved from
            Device Cloud. If a condition is unspecified, an iterator over
            all monitors for this account will be returned.
        :type condition: :class:`.Expression` or None
        :param int page_size: The number of results to fetch in a single page.
        :return: Generator yielding :class:`.DeviceCloudMonitor` instances matching the
            provided conditions.
        """
        params = {'page_size': page_size}
        if condition is not None:
            params['condition'] = condition.to_dict()

        while True:
            response = self._client.get('/monitors', params=params)
            data = response.json()

            for item in data.get('monitors', []):
                yield self._create_monitor(item)

            next_page = data.get('next_page')
            if not next_page:
                break
            params['page'] = next_page 

def hwc_mixed_004_02(self, span_element):
        """
        adds an <intro>, <act> or <conclu> token span to the document.
        """
        for token in span_element.text.split():
            token_id = self._add_token_to_document(token)
            if span_element.tag == 'act':  # doc can have 0+ acts
                self._add_spanning_relation('act_{}'.format(self.act_count),
                                            token_id)
            else:  # <intro> or <conclu>
                self._add_spanning_relation(span_element.tag, token_id)
        if span_element.tag == 'act':
            self.act_count += 1 

def hwc_mixed_004_03(self, data):
        """
        Parse result of L{pyhsm.defines.YSM_BUFFER_LOAD} command.

        @return: Number of bytes now in the YubiHSM internal buffer.
        @rtype: integer

        @raise pyhsm.exception.YHSM_Error: Unexpected number of bytes were loaded
        """
        # typedef struct {
        #   uint8_t numBytes;                   // Number of bytes in buffer now
        # } YSM_BUFFER_LOAD_RESP;
        count = ord(data[0])
        if self.offset == 0:
            # if offset was 0, the buffer was reset and
            # we can verify the length returned
            if count != self.data_len:
                raise pyhsm.exception.YHSM_Error("Incorrect number of bytes in buffer (got %i, expected %i)" \
                                               % (self.data_len, count))
        return count 

def hwc_mixed_004_04(content, alert_type=None, dismissable=True):
    """
    Render a Bootstrap alert
    """
    button = ""
    if not alert_type:
        alert_type = "info"
    css_classes = ["alert", "alert-" + text_value(alert_type)]
    if dismissable:
        css_classes.append("alert-dismissable")
        button = (
            '<button type="button" class="close" '
            + 'data-dismiss="alert" aria-hidden="true">&times;</button>'
        )
    button_placeholder = "__BUTTON__"
    return mark_safe(
        render_tag(
            "div",
            attrs={"class": " ".join(css_classes)},
            content=button_placeholder + text_value(content),
        ).replace(button_placeholder, button)
    ) 

def agc_mixed_004_05(termname, dtype, missing_value):
    """
    Validate a `dtype` and `missing_value` passed to Term.__new__.

    Ensures that we know how to represent ``dtype``, and that missing_value
    is specified for types without default missing values.

    Returns
    -------
    validated_dtype, validated_missing_value : np.dtype, any
        The dtype and missing_value to use for the new term.

    Raises
    ------
    DTypeNotSpecified
        When no dtype was passed to the instance, and the class doesn't
        provide a default.
    NotDType
        When either the class or the instance provides a value not
        coercible to a numpy dtype.
    NoDefaultMissingValue
        When dtype requires an explicit missing_value, but
        ``missing_value`` is NotSpecified.
    """
    import numpy as np
    from .exceptions import DTypeNotSpecified, NotDType, NoDefaultMissingValue
    from .constants import NotSpecified

    if dtype is NotSpecified:
        raise DTypeNotSpecified(f"dtype not specified for {termname}")

    try:
        validated_dtype = np.dtype(dtype)
    except (TypeError, ValueError):
        raise NotDType(f"Invalid dtype {dtype} for {termname}")

    if validated_missing_value := missing_value:
        pass
    elif validated_dtype.kind in 'if':
        raise NoDefaultMissingValue(
            f"dtype {validated_dtype} requires an explicit missing_value for {termname}"
        )
    else:
        validated_missing_value = np.nan if validated_dtype.kind == 'f' else None

    return validated_dtype, validated_missing_value 

def agc_mixed_004_06(alignment):
    # TODO Review documentation and consider for inclusion in API.
    """Clusters alignments
    Takes an alignment created by min_edit_distance_align() and groups
    consecutive errors together. This is useful, because there are often
    many possible alignments, and so often we can't meaningfully distinguish
    between alignment errors at the character level, so it makes many-to-many
    mistakes more readable."""

    clusters = []
    current_cluster = None

    for op, start, end in alignment:
        if op == 'equal':
            if current_cluster:
                clusters.append(current_cluster)
                current_cluster = None
        else:
            if current_cluster:
                current_cluster.append((op, start, end))
            else:
                current_cluster = [(op, start, end)]

    if current_cluster:
        clusters.append(current_cluster)

    return clusters
