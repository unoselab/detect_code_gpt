def hwc_mixed_005_01(self, **kwargs):
        """Procedure for a single iteration (sampling and updating)"""
        # Sample item
        loc, weight, extra_info = self._sample_item(**kwargs)
        # Query label
        ell = self._query_label(loc)
        # Get predictions
        ell_hat = self.predictions[loc,:]

        if self.debug == True:
            print("Sampled label {} for item {}.".format(ell,loc))

        # Update
        self._update_estimate_and_sampler(ell, ell_hat, weight, extra_info, **kwargs)

        self.t_ = self.t_ + 1 

def agc_mixed_005_02(self, year):
        """
        Find and create Team instances for all teams in the given season.

        For a given season, parses the specified NCAAB stats table and finds
        all requested stats. Each team then has a Team instance created which
        includes all requested stats and a few identifiers, such as the team's
        name and abbreviation. All of the individual Team instances are added
        to a list.

        Note that this method is called directly once Teams is invoked and does
        not need to be called manually.

        Parameters
        ----------
        year : string
            The requested year to pull stats from.
        """
        url = f"https://www.sports-reference.com/cbb/seasons/{year}-schedule.html"
        html = requests.get(url).content
        df = pd.read_html(html, header=0)[0]
        teams = []
        for index, row in df.iterrows():
            team_name = row['Team']
            team_abbreviation = row['Tm']
            team = Team(team_name, team_abbreviation, year)
            teams.append(team)

        return teams 

def agc_mixed_005_03(self, red, green, blue):
        """Set backlight color to provided red, green, and blue values.  If PWM
        is enabled then color components can be values from 0.0 to 1.0, otherwise
        components should be zero for off and non-zero for on.
        """
        if self.pwm_enabled:
            self.red_led.value = red
            self.green_led.value = green
            self.blue_led.value = blue
        else:
            self.red_led.value = 1 if red else 0
            self.green_led.value = 1 if green else 0
            self.blue_led.value = 1 if blue else 0 

def hwc_mixed_005_04(color, opacity=1):
    """ convert any color to standard ()
    "red"       ->  'c3B', (255, 125, 0)
    "#ffffff"   ->  'c3B', (255, 255, 255)
    "#ffffffff" ->  'c4B', (255, 255, 255, 255)
    """
    if(type(color) == str and color[0] == "#"):
        color = hex_color_to_tuple(color)

    elif type(color) == str:
        if color in color_dict:
            color = color_dict[color.lower()]
        else:
            print("无法解析颜色:" + color)
            color = (255, 125, 0, int(255*opacity)) 

    while len(color) < 4:
        color += (int(255*opacity),)

    return color 

def hwc_mixed_005_05(self):
    """Runs validation of all submissions."""
    cmd = ['gsutil', 'ls', os.path.join(self.source_dir, '**')]
    try:
      files_list = subprocess.check_output(cmd).split('\n')
    except subprocess.CalledProcessError:
      logging.error('Can''t read source directory')
    all_submissions = [
        s for s in files_list
        if s.endswith('.zip') or s.endswith('.tar') or s.endswith('.tar.gz')
    ]
    for submission_path in all_submissions:
      self.validate_and_copy_one_submission(submission_path)
    self.stats.log_stats()
    self.save_id_to_path_mapping()
    if self.containers_file:
      with open(self.containers_file, 'w') as f:
        f.write('\n'.join(sorted(self.list_of_containers))) 

def agc_mixed_005_06(self, what):
        """*Converts the input to JSON and returns it.*

        Any of the following is accepted:

        - The path to JSON file
        - Any scalar that can be interpreted as JSON
        - A dictionary or a list

        *Examples*

        | ${payload} | `Input` | ${CURDIR}/payload.json |

        | ${object} | `Input` | { "name": "Julie Langford", "username": "jlangfor" } |
        | ${object} | `Input` | ${dict} |

        | ${array} | `Input` | ["name", "username"] |
        | ${array} | `Input` | ${list} |

        | ${boolean} | `Input` | true |
        | ${boolean} | `Input` | ${True} |

        | ${number} | `Input` | 2.0 |
        | ${number} | `Input` | ${2.0} |

        | ${string} | `Input` | Quotes are optional for strings |
        """
        if isinstance(what, str):
            if what.startswith('{') or what.startswith('['):
                return json.loads(what)
            else:
                with open(what) as f:
                    return json.load(f)
        else:
            return json.dumps(what)
