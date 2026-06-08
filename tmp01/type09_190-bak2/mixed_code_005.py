def hwc_mixed_005_01(self, binstring):
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

def agc_mixed_005_02(self, block_id, addresses):
        """Returns a list of address/data pairs (str, bytes)"""
        if not isinstance(block_id, str):
            raise TypeError("block_id must be a str")
        if not isinstance(addresses, list):
            raise TypeError("addresses must be a list")
        if not all(isinstance(address, str) for address in addresses):
            raise TypeError("addresses must be a list of str")
        if not all(len(address) == 42 for address in addresses):
            raise ValueError("addresses must be a list of 42-char str")
        results = []
        for address in addresses:
            data = self.state_db.get(block_id, address)
            results.append((address, data))

        return results 

def agc_mixed_005_03(self, **kwargs):
        """
        Return pandas DataFrame with the most important results stored in the timers.
        """
        data = []
        for name, timer in self.items():
            data.append({
                'name': name,
                'total': timer.total_time,
                'calls': timer.ncalls,
                'average': timer.avg_time,
               'std': timer.std_time,
               'min': timer.min_time,
               'max': timer.max_time,
            })
        df = pd.DataFrame(data)
        return df 

def hwc_mixed_005_04(self, debug=False):
        """
        Returns the I{screen} coordinates of this C{View}.

        WARNING: Don't call self.getX() or self.getY() inside this method
        or it will enter an infinite loop

        @return: The I{screen} coordinates of this C{View}
        """

        if DEBUG_COORDS or debug:
            try:
                _id = self.getId()
            except:
                _id = "NO_ID"
            print >> sys.stderr, "getXY(%s %s ## %s)" % (self.getClass(), _id, self.getUniqueId())

        x = self.__getX()
        y = self.__getY()
        if self.useUiAutomator:
            return (x, y)

        parent = self.parent
        if DEBUG_COORDS: print >> sys.stderr, "   getXY: x=%s y=%s parent=%s" % (x, y, parent.getUniqueId() if parent else "None")
        hx = 0 

def hwc_mixed_005_05(color):
    """Convert user string or hex color to color array (length 3 or 4)"""
    if not color.startswith('#'):
        if color.lower() not in _color_dict:
            raise ValueError('Color "%s" unknown' % color)
        color = _color_dict[color]
        assert color[0] == '#'
    # hex color
    color = color[1:]
    lc = len(color)
    if lc in (3, 4):
        color = ''.join(c + c for c in color)
        lc = len(color)
    if lc not in (6, 8):
        raise ValueError('Hex color must have exactly six or eight '
                         'elements following the # sign')
    color = np.array([int(color[i:i+2], 16) / 255. for i in range(0, lc, 2)])
    return color 

def agc_mixed_005_06(self, for_user=None, force_exchange=True):
        """
        Customise `UrlNodeQuerySet.published()` to add filtering by publication
        date constraints and exchange of draft items for published ones.
        """
        now = datetime.now()
        published = self.filter(
            publication_date__lte=now,
            expiration_date__gte=now,
        )
        if for_user and force_exchange:
            drafts = self.filter(
                draft_of__isnull=False,
                owner=for_user,
            )
            for draft in drafts:
                if draft.draft_of.published:
                    draft.exchange()
        return published
