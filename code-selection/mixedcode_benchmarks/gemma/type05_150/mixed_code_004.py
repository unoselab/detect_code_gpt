def hwc_mixed_004_01(indices):
    """Generator over all possible blackboxings of these indices.

    Args:
        indices (tuple[int]): Nodes to blackbox.

    Yields:
        Blackbox: The next |Blackbox| of ``indices``.
    """
    for partition in all_partitions(indices):
        # TODO? don't consider the empty set here
        # (pass `nonempty=True` to `powerset`)
        for output_indices in utils.powerset(indices):
            blackbox = Blackbox(partition, output_indices)
            try:  # Ensure every box has at least one output
                validate.blackbox(blackbox)
            except ValueError:
                continue
            yield blackbox 

def hwc_mixed_004_02(records):
    """
    Reverse the order of sites in sequences.
    """
    logging.info('Applying _reverse_sequences generator: '
                 'reversing the order of sites in sequences.')
    for record in records:
        rev_record = SeqRecord(record.seq[::-1], id=record.id,
                               name=record.name,
                               description=record.description)
        # Copy the annotations over
        _reverse_annotations(record, rev_record)

        yield rev_record 

def agc_mixed_004_03(self, qname):
        """
        Show information about Queue
        """
        queue = self.get_queue(qname)
        if not queue:
            print(f"Queue {qname} not found.")
            return

        info = {
            "name": queue.name,
            "size": queue.size(),
            "status": queue.status,
            "created": queue.created_at
        }

        for key, value in info.items():
            print(f"{key.capitalize()}: {value}") 

def agc_mixed_004_04(env, args):
    """Raises an ArgumentError if the given arguments are not valid."""

    if not isinstance(args, dict):
        raise ArgumentError("Arguments must be provided as a dictionary.")

    for key, value in args.items():
        if key not in env.valid_arguments:
            raise ArgumentError(f"Invalid argument: {key}")

        expected_type = env.valid_arguments[key]
        if not isinstance(value, expected_type):
            raise ArgumentError(
                f"Argument {key} must be of type {expected_type.__name__}, "
                f"got {type(value).__name__} instead."
            ) 

def agc_mixed_004_05(self):
        """Returns an array of dictionaries, each dictionary represents an
        analysis row to be rendered in the list. The array returned is sorted
        in accordance with the layout positions set for the analyses this
        worksheet contains when the analyses were added in the worksheet.

        :returns: list of dicts with the items to be rendered in the list
        """
        items = []
        for analysis in sorted(self.analyses, key=lambda x: x.layout_position):
            items.append({
                'id': analysis.id,
                'name': analysis.name,
                'layout_position': analysis.layout_position,
                'status': analysis.status,
                'type': analysis.type
            })
        return items 

def hwc_mixed_004_06(self, indicators, enclave_ids=None, is_enclave=True,
                                    page_size=None, page_number=None):
        """
        Retrieves a page of all TruSTAR reports that contain the searched indicators.

        :param indicators: A list of indicator values to retrieve correlated reports for.
        :param enclave_ids: The enclaves to search in.
        :param is_enclave: Whether to search enclave reports or community reports.
        :param int page_number: the page number to get.
        :param int page_size: the size of the page to be returned.
        :return: The list of IDs of reports that correlated.

        Example:

        >>> reports = ts.get_correlated_reports_page(["wannacry", "www.evil.com"]).items
        >>> print([report.id for report in reports])
        ["e3bc6921-e2c8-42eb-829e-eea8da2d3f36", "4d04804f-ff82-4a0b-8586-c42aef2f6f73"]
        """

        if is_enclave:
            distribution_type = DistributionType.ENCLAVE
        else:
            distribution_type = DistributionType.COMMUNITY

        params = {
            'indicators': indicators,
            'enclaveIds': enclave_ids,
            'distributionType': distribution_type,
            'pageNumber': page_number,
            'pageSize': page_size
        }
        resp = self._client.get("reports/correlated", params=params)

        return Page.from_dict(resp.json(), content_type=Report)
