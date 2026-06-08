def hwc_mixed_001_01(sub_parser: ArgumentParser) -> ArgumentParser:
    """Populates the sub parser with the shell arguments"""

    sub_parser.add_argument(
        '-p', '--project',
        dest='project_directory',
        type=str,
        default=None
    )

    sub_parser.add_argument(
        '-l', '--log',
        dest='logging_path',
        type=str,
        default=None
    )

    sub_parser.add_argument(
        '-o', '--output',
        dest='output_directory',
        type=str,
        default=None
    )

    sub_parser.add_argument(
        '-s', '--shared',
        dest='shared_data_path',
        type=str,
        default=None
    )

    return sub_parser 

def agc_mixed_001_02(self, lat, lon):
        """Get the altitude of a lat lon pair, using the four neighbouring
            pixels for interpolation.
        """
        # print "-----\nFromLatLon", lon, lat
        lat_min = lat - self.lat_step
        lat_max = lat + self.lat_step
        lon_min = lon - self.lon_step
        lon_max = lon + self.lon_step
        # get the four neighbouring altitudes
        alt_min = self.getAltitude(lat_min, lon_min)
        alt_max = self.getAltitude(lat_max, lon_max)
        alt_min_2 = self.getAltitude(lat_min, lon)
        alt_max_2 = self.getAltitude(lat_max, lon)
        # interpolate the altitude
        alt = alt_min + (alt_max - alt_min) * (lat - lat_min) / (lat_max - lat_min)
        alt = alt + (alt_max_2 - alt) * (lon - lon_min) / (lon_max - lon_min)
        return alt 

def hwc_mixed_001_03(self, plaintext):
        """Return ciphertext for given plaintext."""

        # String to bytes.
        plainbytes = plaintext.encode('utf8')

        # Compress plaintext bytes.
        compressed = zlib.compress(plainbytes)

        # Construct AES-GCM cipher, with 96-bit nonce.
        cipher = AES.new(self.cipher_key, AES.MODE_GCM, nonce=random_bytes(12))

        # Encrypt and digest.
        encrypted, tag = cipher.encrypt_and_digest(compressed)

        # Combine with nonce.
        combined = cipher.nonce + tag + encrypted

        # Encode as Base64.
        cipherbytes = base64.b64encode(combined)

        # Bytes to string.
        ciphertext = cipherbytes.decode('utf8')

        # Return ciphertext.
        return ciphertext 

def agc_mixed_001_04():
    """
    Build an argument parser using optparse. Use it when python version is 2.5 or 2.6.

    """
    parser = optparse.OptionParser(usage="usage: %prog [options]")
    parser.add_option("-i", "--input", dest="input",
                      help="Input file")
    parser.add_option("-o", "--output", dest="output",
                      help="Output file")
    parser.add_option("-t", "--type", dest="type",
                      help="Type of the input file")
    parser.add_option("-f", "--format", dest="format",
                      help="Format of the output file")
    parser.add_option("-d", "--debug", dest="debug",
                      help="Debug mode", action="store_true")
    return parser 

def hwc_mixed_001_05(deps, tree_base, saltenv='base'):
    """
    Get include string for list of dependent rpms to build package
    """
    deps_list = ''
    if deps is None:
        return deps_list
    if not isinstance(deps, list):
        raise SaltInvocationError(
            '\'deps\' must be a Python list or comma-separated string'
        )
    for deprpm in deps:
        parsed = _urlparse(deprpm)
        depbase = os.path.basename(deprpm)
        dest = os.path.join(tree_base, depbase)
        if parsed.scheme:
            __salt__['cp.get_url'](deprpm, dest, saltenv=saltenv)
        else:
            shutil.copy(deprpm, dest)

        deps_list += ' {0}'.format(dest)

    return deps_list 

def agc_mixed_001_06 (self, current_password, new_password):
        """
            Change the password for the current user

            @param current_password (string) - md5 hash of the current password of the user
            @param new_password (string) - md5 hash of the new password of the user (make sure to doublecheck!)

            @return (bool) - Boolean indicating whether ChangePassword was successful.
        """
        if self.UsersCheckPassword (current_password) == True:

            # Check if the new password is valid
            if self.UsersCheckPassword (new_password) == True:

                # Change the password
                self.Users.password = new_password

                # Return True
                return True

            # Return False
            return False

        # Return False
        return False
