def hwc_mixed_005_01(self, dirname):
        """Returns whether the path is a directory or not."""
        client = boto3.client("s3")
        bucket, path = self.bucket_and_path(dirname)
        if not path.endswith("/"):
            path += "/"  # This will now only retrieve subdir content
        r = client.list_objects(Bucket=bucket, Prefix=path, Delimiter="/")
        if r.get("Contents") or r.get("CommonPrefixes"):
            return True
        return False 

def hwc_mixed_005_02(self, span):
        """
        Convert the passed BasicSpan into an JsonSpan and
        add it to the span queue
        """
        if instana.singletons.agent.can_send() or "INSTANA_TEST" in os.environ:
            json_span = None

            if span.operation_name in self.registered_spans:
                json_span = self.build_registered_span(span)
            else:
                json_span = self.build_sdk_span(span)

            self.queue.put(json_span) 

def hwc_mixed_005_03(self):
        """ The border width in visual coordinates
        """
        render_to_doc =  \
            self.transforms.get_transform('document', 'visual')

        vec = render_to_doc.map([self.border_width, self.border_width, 0])
        origin = render_to_doc.map([0, 0, 0])

        visual_border_width = [vec[0] - origin[0], vec[1] - origin[1]]

        # we need to flip the y axis because coordinate systems are inverted
        visual_border_width[1] *= -1

        return visual_border_width 

def agc_mixed_005_04(dcfg,dp='figs',force=False):
    """
    'figi','plotp'
    """
    import os
    import matplotlib.pyplot as plt

    if not os.path.exists(dp):
        os.makedirs(dp)

    for figi, plotp in dcfg.items():
        path = os.path.join(dp, f"{figi}.png")
        if force or not os.path.exists(path):
            plt.figure()
            plotp()
            plt.savefig(path)
            plt.close() 

def agc_mixed_005_05(urlinfo, shorter_keys=True):
    """ Takes a urlinfo object and returns a flat dictionary."""
    flat = {}
    for key, value in urlinfo.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                new_key = sub_key if shorter_keys else f"{key}_{sub_key}"
                flat[new_key] = sub_value
        else:
            flat[key] = value
    return flat 

def agc_mixed_005_06(func):
    """Get signature parameters

    Support Cython functions by grabbing relevant attributes from the Cython
    function and attaching to a no-op function. This is somewhat brittle, since
    funcsigs may change, but given that funcsigs is written to a PEP, we hope
    it is relatively stable. Future versions of Python may allow overloading
    the inspect 'isfunction' and 'ismethod' functions / create ABC for Python
    functions. Until then, it appears that Cython won't do anything about
    compatability with the inspect module.

    Args:
        func: The function whose signature should be checked.

    Raises:
        TypeError: A type error if the signature is not supported
    """
    # The first condition for Cython functions, the latter for Cython instance
    # methods
    import inspect

    try:
        return inspect.signature(func).parameters
    except (ValueError, TypeError):
        if hasattr(func, '__cython_func_sig__'):
            def wrapper(*args, **kwargs):
                pass
            wrapper.__cython_func_sig__ = func.__cython_func_sig__
            return inspect.signature(wrapper).parameters
        raise TypeError(f"Signature not supported for {func}")
