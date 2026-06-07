def agc_mixed_002_01(self,cutoff):
        """
        This function defines the residues for plotting in case only a topology file has been submitted.
        In this case the residence time analysis in not necessary and it is enough just to find all
        residues within a cutoff distance.
            Takes:
                * cutoff * - cutoff distance in angstroms that defines native contacts
            Output:
                *
        """

        #self.protein_selection = self.universe.select_atoms('all and around '+str(cutoff)+' (segid '+str(self.universe.ligand.segids[0])+' and resid '+str(self.universe.ligand.resids[0])+')')
        #The previous line was not working on some examples for some reason - switch to more efficient Neighbour Search
        self.residues_for_plotting = []
        for residue1 in self.residues:
            for residue2 in self.residues:
                if residue1!= residue2:
                    distance = calculate_distance(residue1.coordinates, residue2.coordinates)
                    if distance <= cutoff:
                        self.residues_for_plotting.append(residue1)
                        self.residues_for_plotting.append(residue2)
                        break 

def hwc_mixed_002_02(self):
        """For each file in noseOfYeti/specs, output nodes to represent each spec file"""
        tokens = []
        section = nodes.section()
        section['ids'].append("available-tasks")

        title = nodes.title()
        title += nodes.Text("Default tasks")
        section += title

        task_finder = TaskFinder(Collector())
        for name, task in sorted(task_finder.default_tasks().items(), key=lambda x: len(x[0])):

            lines = [name] + ["  {0}".format(line.strip()) for line in task.description.split('\n')]
            viewlist = ViewList()
            for line in lines:
                viewlist.append(line, name)
            self.state.nested_parse(viewlist, self.content_offset, section)

        return [section] 

def agc_mixed_002_03(color, opacity=1):
    """ convert any color to standard ()
    "red"       ->  'c3B', (255, 125, 0)
    "#ffffff"   ->  'c3B', (255, 255, 255)
    "#ffffffff" ->  'c4B', (255, 255, 255, 255)
    """
    if color[0] == '#':
        if len(color) == 7:
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            return 'c3B', (r, g, b)
        elif len(color) == 9:
            r, g, b, a = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16), int(color[7:9], 16)
            return 'c4B', (r, g, b, a)
        else:
            raise ValueError("Invalid color format")
    elif color in colorsys.cnames:
        r, g, b = colorsys.cnames[color]
        return 'c3B', (r, g, b)
    else:
        raise ValueError("Invalid color format") 

def hwc_mixed_002_04 (self, separator=",", file=sys.stdout):
                """dump as a comma separated value file"""
                for row in range(1, self.maxRow + 1):
                        sep = ""
                        for column in range(1, self.maxColumn + 1):
                                file.write("%s\"%s\"" % (sep, self.GetCellValue(column, row, "")))
                                sep = separator
                        file.write("\n") 

def hwc_mixed_002_05(self):
        """Updates questions known to this Section"""
        if self.is_simple_section():
            return  # we don't need to go through any this for simple sections
        # ideally, we would update the parts map and questions list
        # at the same time as _get_parts(), to not run into the
        # issue where magic parts are initialized (with items)
        # ignorant of their "sibling" magic part items...
        # because the section hasn't been updated or saved to database
        part_list = self._get_parts()
        if len(part_list) > len(self._my_map['assessmentParts']):
            self._update_assessment_parts_map(part_list)
            self._update_questions_list(part_list)
            self._save() 

def agc_mixed_002_06(self, name, default_value=None):
        """Retrieve a value from DB"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"SELECT value FROM my_table WHERE name = '{name}'")
                result = cursor.fetchone()
                if result:
                    return result[0]
                else:
                    return default_value
        except Exception as e:
            print(f"Error: {e}")
            return default_value
