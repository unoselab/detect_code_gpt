def agc_mixed_004_01(align_bams, ref_file, items):
    """Ensure inputs to calling are indexed as expected.
    """
    if not align_bams:
        raise ValueError("No align_bams provided!")
    if not ref_file:
        raise ValueError("No ref_file provided!")
    if not items:
        raise ValueError("No items provided!")
    if not isinstance(align_bams, list):
        raise TypeError("align_bams must be a list!")
    if not isinstance(ref_file, str):
        raise TypeError("ref_file must be a string!")
    if not isinstance(items, list):
        raise TypeError("items must be a list!")
    for bam in align_bams:
        if not bam.endswith(".bam"):
            raise ValueError("All align_bams must be BAM files!")
    for item in items:
        if not isinstance(item, str):
            raise TypeError("All items must be strings!") 

def agc_mixed_004_02(a, b, scale=1):
    """Intersection between two segments."""
    x1, y1 = a[0], a[1]
    x2, y2 = a[2], a[3]
    x3, y3 = b[0], b[1]
    x4, y4 = b[2], b[3]
    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if denominator == 0:
        return None
    u_a = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denominator
    u_b = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denominator
    if 0 <= u_a <= 1 and 0 <= u_b <= 1:
        x = x1 + u_a * (x2 - x1)
        y = y1 + u_a * (y2 - y1)
        return (x * scale, y * scale)
    else:
        return None 

def agc_mixed_004_03(self):
        """
        Returns errors on:
        Certificate, PrivateKey or Chain not being properly formatted
        Arn not existing if its provided
        PrivateKey size > 2048
        Certificate expired or is not yet in effect

        Does not return errors on:
        Checking Certificate is legit, or a selfsigned chain is provided

        :return: str(JSON) for response
        """
        errors = []
        if not self.certificate:
            errors.append("Certificate not properly formatted")
        if not self.private_key:
            errors.append("PrivateKey not properly formatted")
        if not self.chain:
            errors.append("Chain not properly formatted")
        if self.arn and not self.certificate_manager.get_certificate(self.arn):
            errors.append("Arn not existing")
        if len(self.private_key) > 2048:
            errors.append("PrivateKey size > 2048")
        if self.certificate.not_valid_before > datetime.now() or self.certificate.not_valid_after < datetime.now():
            errors.append("Certificate expired or is not yet in effect")
        return json.dumps(errors) 

def hwc_mixed_004_04(self):
        """
        Returns combined size in bytes for all repository files
        """

        size = 0
        try:
            tip = self.get_changeset()
            for topnode, dirs, files in tip.walk('/'):
                for f in files:
                    size += tip.get_file_size(f.path)
                for dir in dirs:
                    for f in files:
                        size += tip.get_file_size(f.path)

        except RepositoryError:
            pass
        return size 

def hwc_mixed_004_05(self, field_name, field_body):
        """Fill content into nodes.

        :param string field_name: Field name of the field
        :param field_name: Field body if the field
        :type field_name: str or instance of docutils.nodes
        :return: field instance filled with given name and body
        :rtype: nodes.field

        """
        name = nodes.field_name()
        name += nodes.Text(field_name)

        paragraph = nodes.paragraph()
        if isinstance(field_body, str):
            # This is the case when field_body is just a string:
            paragraph += nodes.Text(field_body)
        else:
            # This is the case when field_body is a complex node:
            # useful when constructing nested field lists
            paragraph += field_body

        body = nodes.field_body()
        body += paragraph

        field = nodes.field()
        field.extend([name, body])
        return field 

def hwc_mixed_004_06(self, binstring):
        """Same as _setbin_safe, but input isn't sanity checked. binstring mustn't start with '0b'."""
        length = len(binstring)
        # pad with zeros up to byte boundary if needed
        boundary = ((length + 7) // 8) * 8
        padded_binstring = binstring + '0' * (boundary - length)\
                           if len(binstring) < boundary else binstring
        try:
            bytelist = [int(padded_binstring[x:x + 8], 2)
                        for x in xrange(0, len(padded_binstring), 8)]
        except ValueError:
            raise CreationError("Invalid character in bin initialiser {0}.", binstring)
        self._setbytes_unsafe(bytearray(bytelist), length, 0)
