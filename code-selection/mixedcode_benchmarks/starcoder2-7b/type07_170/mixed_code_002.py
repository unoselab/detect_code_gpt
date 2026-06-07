def hwc_mixed_002_01(p):
    """ function_body : program_co END FUNCTION
                      | program_co END SUB
                      | statements_co END FUNCTION
                      | statements_co END SUB
                      | co_statements_co END FUNCTION
                      | co_statements_co END SUB
                      | END FUNCTION
                      | END SUB
    """
    if not FUNCTION_LEVEL:
        syntax_error(p.lineno(3), "Unexpected token 'END %s'. No Function or Sub has been defined." % p[2])
        p[0] = None
        return

    a = FUNCTION_LEVEL[-1].kind
    if a not in (KIND.sub, KIND.function):  # This function/sub was not correctly declared, so exit now
        p[0] = None
        return

    i = 2 if p[1] == 'END' else 3
    b = p[i].lower()

    if a != b:
        syntax_error(p.lineno(i), "Unexpected token 'END %s'. Should be 'END %s'" % (b.upper(), a.upper()))
        p[0] = None
    else:
        p[0] = None if p[1] == 'END' else p[1] 

def hwc_mixed_002_02(self):
        """
        Resets the :any:`Pipette` tip tracking, "refilling" the tip racks
        """
        self.current_tip(None)
        self.tip_rack_iter = iter([])

        if self.has_tip_rack():
            iterables = self.tip_racks

            if self.channels > 1:
                iterables = [c for rack in self.tip_racks for c in rack.cols]
            else:
                iterables = [w for rack in self.tip_racks for w in rack]

            if self.starting_tip:
                iterables = iterables[iterables.index(self.starting_tip):]

            self.tip_rack_iter = itertools.chain(iterables) 

def hwc_mixed_002_03(self, field_name, field_vals, sort_dir_str):
        """
        allow sorting by a set of values

        http://stackoverflow.com/questions/3303851/sqlite-and-custom-order-by
        """
        fvi = None
        if sort_dir_str == 'ASC':
            fvi = (t for t in enumerate(field_vals)) 

        else:
            fvi = (t for t in enumerate(reversed(field_vals))) 

        query_sort_str = ['  CASE {}'.format(self._normalize_name(field_name))]
        query_args = []
        for i, v in fvi:
            query_sort_str.append('    WHEN {} THEN {}'.format(self.val_placeholder, i))
            query_args.append(v)

        query_sort_str.append('  END')
        query_sort_str = "\n".join(query_sort_str)
        return query_sort_str, query_args 

def agc_mixed_002_04(self, tol=0.2):
        """
        Determines the covalent bonds in a molecule.

        Args:
            tol (float): The tol to determine bonds in a structure. See
                CovalentBond.is_bonded.

        Returns:
            List of bonds
        """
        return [
            CovalentBond(
                atom1=self.atoms[i],
                atom2=self.atoms[j],
                distance=self.get_distance(i, j),
                angle=self.get_angle(i, j, k),
                dihedral=self.get_dihedral(i, j, k, l),
            )
            for i, j, k, l in self.get_bonds()
            if self.get_distance(i, j) < tol
        ] 

def agc_mixed_002_05(self, utc_time, lon, lat, alt):
        """Calculate observers look angle to a satellite.
        http://celestrak.com/columns/v02n02/

        utc_time: Observation time (datetime object)
        lon: Longitude of observer position on ground in degrees east
        lat: Latitude of observer position on ground in degrees north
        alt: Altitude above sea-level (geoid) of observer position on ground in km

        Return: (Azimuth, Elevation)
        """

        lon = lon * np.pi / 180
        lat = lat * np.pi / 180

        # Convert to geocentric position
        r = self.get_geocentric_position(utc_time, lon, lat, alt)

        # Convert to geocentric velocity
        v = self.get_geocentric_velocity(utc_time, lon, lat, alt)

        # Calculate look angle
        azimuth = np.arctan2(v[0], v[1])
        elevation = np.arctan2(v[2], np.sqrt(v[0]**2 + v[1]**2))

        # Convert to degrees
        azimuth = azimuth * 180 / np.pi
        elevation = elevation * 180 / np.pi

        return azimuth, elevation 

def agc_mixed_002_06(self):
        """
        Send verification email to this users email address.

        Remember that the verification email may end up in the users spam
        folder.
        """
        if self.is_verified:
            raise ValueError('User is already verified.')

        token = self.generate_verification_token()
        self.verification_token = token
        self.save()

        verification_url = self.get_verification_url(token)
        send_mail(
            'Verify your email address',
            'Please click the following link to verify your email address:\n\n'
            '{}'.format(verification_url),
            settings.DEFAULT_FROM_EMAIL,
            [self.email],
            fail_silently=False,
        )
