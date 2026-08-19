def agc_mixed_002_01(request):
    """
    This function handles the filtering of available eventregistration-related
    invoice items and is used on the revenue reporting form.
    """
    guest_list = []
    event_id = request.GET.get('event_id')
    if event_id:
        from apps.event_registration.models import EventRegistration
        registrations = EventRegistration.objects.filter(event_id=event_id)
        for reg in registrations:
            guest_list.append({
                'id': reg.id,
                'name': reg.guest_name,
                'email': reg.guest_email
            })
    return guest_list 

def hwc_mixed_002_02():
    """This method attempts to auto-generate a unique cryptographic key based on the hardware ID.
    It should *NOT* be used in production, or to replace a proper key, but it can help get will
    running in local and test environments more easily."""
    import uuid
    import time
    import random
    import hashlib

    node = uuid.getnode()

    h = hashlib.md5()
    h.update(str("%s" % node).encode('utf-8'))
    key1 = h.hexdigest()

    time.sleep(random.uniform(0, 0.5))
    node = uuid.getnode()

    h = hashlib.md5()
    h.update(str("%s" % node).encode('utf-8'))
    key2 = h.hexdigest()

    time.sleep(random.uniform(0, 0.5))
    node = uuid.getnode()

    h = hashlib.md5()
    h.update(str("%s" % node).encode('utf-8'))
    key3 = h.hexdigest()

    if key1 == key2 and key2 == key3:
        return key1

    return False 

def agc_mixed_002_03(version):
    """
    Split a version string into major, minor, and bugfix numbers.  If any of
    those numbers are missing the default is zero.  Any pre/post release
    modifiers are ignored.

    Examples
    ========
    >>> _version_split('1.2.3')
    (1, 2, 3)
    >>> _version_split('1.2')
    (1, 2, 0)
    >>> _version_split('1.2rc1')
    (1, 2, 0)
    >>> _version_split('1')
    (1, 0, 0)
    >>> _version_split('')
    (0, 0, 0)
    """

    import re
    parts = re.split(r'[^0-9]+', version)
    nums = []
    for p in parts:
        if p.isdigit():
            nums.append(int(p))
        elif not p and not nums:
            continue
        else:
            break

    res = [0, 0, 0]
    for i in range(min(len(nums), 3)):
        res[i] = nums[i]
    return tuple(res) 

def hwc_mixed_002_04(kw):
    """
    Internal helper. Extracts a reason (possibly both reasons!) from
    the kwargs for a circuit failed or closed event.
    """
    try:
        # we "often" have a REASON
        reason = kw['REASON']
        try:
            # ...and sometimes even have a REMOTE_REASON
            reason = '{}, {}'.format(reason, kw['REMOTE_REASON'])
        except KeyError:
            pass  # should still be the 'REASON' error if we had it
    except KeyError:
        reason = "unknown"
    return reason 

def hwc_mixed_002_05(text):
    """
    Returns a list of simplified and stemmed down terms for the inputted text.

    This will remove common terms and words from the search and return only
    the important root terms.  This is useful in searching algorithms.

    :param      text | <str>

    :return     [<str>, ..]
    """
    terms = re.split('\s*', toAscii(text))

    output = []
    for term in terms:
        # ignore apostrophe's
        if term.endswith("'s"):
            stripped_term = term[:-2]
        else:
            stripped_term = term

        single_term = singularize(stripped_term)

        if term in COMMON_TERMS or stripped_term in COMMON_TERMS or single_term in COMMON_TERMS:
            continue

        output.append(single_term)

    return output 

def agc_mixed_002_06(self, ipstr):
        """
        Convenience method to verify if string is an IP addr?
        :param ipstr: Stinrg containing IP address
        :rtype True if string is a valid IP address
        """
        import socket
        try:
            socket.inet_pton(socket.AF_INET, ipstr)
            return True
        except socket.error:
            try:
                socket.inet_pton(socket.AF_INET6, ipstr)
                return True
            except socket.error:
                return False
