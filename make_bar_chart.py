import matplotlib.pyplot as plt
import numpy as np

COMMIT_MSG_CHAR_LIMIT = 20

# Fixing random state for reproducibility
np.random.seed(19680801)


plt.rcdefaults()
fig, ax = plt.subplots()

# Example data
people = ('2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
'2021-08-01 0fc232 commit message here', 
)
y_pos = np.arange(len(people))
x_vals = .01 * np.random.rand(len(people))
error = np.random.rand(len(people))

# ax.barh(y_pos, x_vals, xerr=error, align='center')
ax.barh(y_pos, x_vals, align='center')
ax.set_yticks(y_pos)
ax.set_yticklabels(people)
ax.invert_yaxis()  # labels read top-to-bottom
ax.set_xlabel('Current consumption avg (A) \nblue=avg, black=(min and max)')
ax.set_title('First 90s')
ax.set_xscale('log')
fig.subplots_adjust(left=0.5)
fig.subplots_adjust(bottom=0.17)
fig.subplots_adjust(right=0.975)
fig.set_size_inches(7, 8)
plt.grid(b=True, which="both", axis="x", color='gray', linestyle='dashed')
ax.set_axisbelow(True)

# zip joins x and y coordinates in pairs
for x,y in zip(x_vals,y_pos):

    label = "{:f}".format(x)

    plt.annotate(label, # this is the text
                 (x,y), # these are the coordinates to position the label
                 textcoords="offset points", # how to position the text
                 xytext=(10,-3), # distance from text to points (x,y)
                 ha='left') # horizontal alignment can be left, right or center
                 
for tick in ax.get_xminorticklabels():
    tick.set_rotation(30)
plt.show()
                 
# plt.savefig(fname="plot.png")