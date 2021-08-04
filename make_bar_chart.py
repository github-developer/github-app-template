# Makes bar chart. 
# 
# Expected input: 
# python make_bar_chart.py "plot1.png" '2021-08-01,0fc232,user here,0.0033'


import matplotlib.pyplot as plt
import numpy as np
import csv
import sys

MAX_LINES_IN_BAR_GRAPH = 25

# 1. Open CSV  
# 2. Make plot
# 3. Delete the first line from the CSV
# 4. Close CSV 

plt.rcdefaults()
fig, ax = plt.subplots()

# Read all the lines of the CSV file and the first argument from the command-line
csv_lines = []
with open('first_few_seconds.csv', "w+", newline='\n') as csvfile:
    spamreader = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in spamreader:
        csv_lines.append(row)
csv_lines.append(sys.argv[2].split(","))

# Split all the lines 
people = []
x_vals = []
for line in csv_lines:
    people.append(line[0] + " " + line[1] + " " + line[2])
    x_vals.append(float(line[3]))
y_pos = np.arange(len(people))
print(x_vals)

# Write all the lines back to the CSV (up to a limit)
if len(csv_lines) > MAX_LINES_IN_BAR_GRAPH:
    csv_lines = csv_lines[1:]
with open('first_few_seconds.csv', 'w', newline='\n') as csvfile:
    spamwriter = csv.writer(csvfile, delimiter=',',
                            quotechar='"', quoting=csv.QUOTE_MINIMAL)
    for line in csv_lines:
        spamwriter.writerow(line)

ax.barh(y_pos, x_vals, align='center')
ax.set_yticks(y_pos)
ax.set_yticklabels(people)
ax.invert_yaxis()  # labels read top-to-bottom
ax.set_xlabel('Current consumption avg (A) \nblue=avg, black=(min and max)')
ax.set_title('First 90s')
ax.set_xscale('log')
fig.subplots_adjust(left=0.5)
fig.subplots_adjust(bottom=0.17)
# fig.subplots_adjust(right=0.975)
fig.set_size_inches(7, 8)
plt.grid(b=True, which="both", axis="x", color='gray', linestyle='dashed')
ax.set_axisbelow(True)

# zip joins x and y coordinates in pairs
for x,y in zip(x_vals,y_pos):

    label = x

    plt.annotate(label, # this is the text
                 (x,y), # these are the coordinates to position the label
                 textcoords="offset points", # how to position the text
                 xytext=(10,-3), # distance from text to points (x,y)
                 ha='left') # horizontal alignment can be left, right or center
                 
for tick in ax.get_xminorticklabels():
    tick.set_rotation(30)
# plt.show()
# plt.savefig(fname="plot.png")
plt.savefig(fname=sys.argv[1])

