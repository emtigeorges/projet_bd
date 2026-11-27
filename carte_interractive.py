# Import the modules (the "tools" we need)
import pandas as pd                          # import pandas to read and handle data tables -> we call it pd
import folium                                # import folium to create interactive maps
import webbrowser                            # import webbrowser to open a file in the browser
from folium.plugins import FastMarkerCluster # import a folium tool to display a lot of points quickly

# Paths to the data folders
# The "r" before the quotes stops Python from reading the "\" as special codes, so they are read as a normal path
data = r"C:\Users\moi\downloads\data\data"   # folder of the main files (support, station, antenna)
ref = r"C:\Users\moi\downloads\ref\ref"      # folder of the reference tables (operator, nature)

# Number of points to display, to reduce lag while testing
NB_POINTS = None


# Function that opens a text file and puts it in a table, so we don't repeat the same code 9 times
def lire(chemin):  # "chemin" = the address of the file to open

    # Opens the file and stores it in a table called "d":
    #   sep=";" -> the columns of the file are separated by ";"
    #   encoding="utf-8"-> so that accents (é, è, ô) display correctly
    #   dtype={"STA_NM_ANFR": str} -> reads this column as text, otherwise the leading 0s
    #                                disappear (0162290002 would become 162290002)
    d = pd.read_csv(chemin, sep=";", encoding="utf-8", dtype={"STA_NM_ANFR": str})

    # Puts the column names in capital letters and removes spaces
    # to avoid errors if a name is written slightly differently
    d.columns = d.columns.str.strip().str.upper()

    return d  # returns the table, ready to use

#Function to group text together
def joindre(s):  # receives a column of values (s)
    # dropna()      : removes empty values
    # astype(str)   : turns everything into text
    # set(...)      : removes duplicates
    # sorted(...)   : sorts in alphabetical order
    # ", ".join(...) : sticks everything together in one sentence separated by commas
    return ", ".join(sorted(set(s.dropna().astype(str))))

support = lire(data + r"\sup_support.txt")           # the supports (pylons, buildings...) with coordinates
station = lire(data + r"\sup_station.txt")           # the installations (operator, date of commissioning)
antenne = lire(data + r"\sup_antenne.txt")           # the antennas of each installation
emetteur = lire(data + r"\sup_emetteur.txt")         # the transmitters of each antenna (technology: GSM, LTE, 5G...)
bande = lire(data + r"\sup_bande.txt")               # the frequency bands of each transmitter
exploitant = lire(ref + r"\sup_exploitant.txt")      # reference table: ADM_ID -> name of the operator
nature = lire(ref + r"\sup_nature.txt")              # reference table: NAT_ID -> type of support
proprio = lire(ref + r"\sup_proprietaire.txt")       # reference table: TPO_ID -> owner of the support
type_antenne = lire(ref + r"\sup_type_antenne.txt")  # reference table: TAE_ID -> type of antenna


# 2. COORDINATES IN DECIMAL DEGREES (latitude longitude)
# In the file we have degrees + minutes + seconds + letter (N/S or E/W).
# Folium wants a single decimal number (e.g. 45.38).

# Latitude = degrees + minutes/60 + seconds/3600
support["LAT"] = (support["COR_NB_DG_LAT"] + support["COR_NB_MN_LAT"] / 60 + support["COR_NB_SC_LAT"] / 3600)
# Multiply by 1 if North, by -1 if South
support["LAT"] = support["LAT"] * support["COR_CD_NS_LAT"].map({"N": 1, "S": -1})
# Longitude = degrees + minutes/60 + seconds/3600
support["LON"] = (support["COR_NB_DG_LON"] + support["COR_NB_MN_LON"] / 60 + support["COR_NB_SC_LON"] / 3600)
# Multiply by 1 if East, by -1 if West
support["LON"] = support["LON"] * support["COR_CD_EW_LON"].map({"E": 1, "W": -1})


# 3. ANTENNAS: number and types, for each support
# Add the label of its type to each antenna (by linking on TAE_ID)
# how="left" = we keep all the antennas even if no type is found
antenne = antenne.merge(type_antenne, on="TAE_ID", how="left")
# Group the antennas by support: one single row per SUP_ID
ant_par_support = antenne.groupby("SUP_ID").agg(
    NB_ANTENNES=("AER_ID", "count"),                 # counts the number of antennas on the support
    TYPES_ANTENNE=("TAE_LB", joindre)                # list of the antenna types, separated by commas
).reset_index()                                      # puts SUP_ID back as a normal column


# 4. TECHNOLOGIES (GSM, LTE, 5G) for each support
# Chain of links: transmitter -> antenna -> support
# Goal: know which technologies exist on each pylon

# A transmitter knows its antenna, but not its pylon. So we need a small "antenna -> pylon" table.
lien_ant = antenne[["STA_NM_ANFR", "AER_ID", "SUP_ID"]]   # [[...]] : keeps only these 3 columns, we throw away the others
lien_ant = lien_ant.drop_duplicates()                      # drop_duplicates() : removes duplicate rows (the same row written twice)

# We attach the pylon (SUP_ID) to each transmitter
emet = emetteur.merge(                  # merge() : links 2 tables, like a SQL join (we stick together the rows that have the same identifier)
    lien_ant,                           # the table to add
    on=["STA_NM_ANFR", "AER_ID"],       # on= : the columns used to find the right row (the installation AND the antenna)
    how="left"                          # how="left" : we keep all the transmitters, even if no pylon is found
)

# Now we build "one sentence of technologies per pylon"
emet_par_support = (
    emet[["SUP_ID", "EMR_LB_SYSTEME"]]  # [[...]] : we keep only the pylon and its technology
    .dropna()                           # dropna() : removes the rows that have an empty cell
    .drop_duplicates()                  # drop_duplicates() : removes duplicates (5G written 10 times for the same pylon → 1 time)
    .groupby("SUP_ID")                  # groupby() : sorts the rows into packs, one pack per pylon
    .agg(TECHNOLOGIES=("EMR_LB_SYSTEME", joindre))  # agg() : for each pack, we apply "joindre", which sticks the technologies together with commas → e.g. "5G NR, LTE 1800"
    .reset_index()                      # reset_index() : puts SUP_ID back as a real column, so we can do another merge afterwards
)


# 5. FREQUENCY BANDS for each support
# Chain of links: band -> transmitter -> antenna -> support
# Goal: know which frequency bands exist on each pylon

# A band knows its transmitter, but not its pylon. We need a "transmitter -> pylon" table.
lien_emet = emet[["STA_NM_ANFR", "EMR_ID", "SUP_ID"]]   # [[...]] : keeps only these 3 columns
lien_emet = lien_emet.drop_duplicates()                  # drop_duplicates() : removes duplicate rows

# We attach the pylon (SUP_ID) to each band
b = bande.merge(                        # merge() : links 2 tables using common identifiers (like a VLOOKUP)
    lien_emet,                          # the table to add
    on=["STA_NM_ANFR", "EMR_ID"],       # on= : the columns used to find the right row (the installation AND the transmitter)
    how="left"                          # how="left" : we keep all the bands, even if no pylon is found
).dropna(subset=["SUP_ID"])             # dropna(subset=[...]) : removes the rows where SUP_ID is empty (bands without a pylon, useless for the map)

# We remove the incomplete bands
b = b.dropna(subset=["BAN_NB_F_DEB", "BAN_NB_F_FIN"])   # dropna(subset=[...]) : removes the rows where the start OR the end of the band is empty

# We build a small text like "700-800 M"
b["BANDE"] = (                          # creates a new column "BANDE"
    b["BAN_NB_F_DEB"].astype(str)       # astype(str) : turns the number into text, so we can stick it together with other texts
    + "-"                               # a dash between the start and the end
    + b["BAN_NB_F_FIN"].astype(str)     # the end of the band, as text
    + " "                               # a space
    + b["BAN_FG_UNITE"].fillna("").astype(str)   # fillna("") : replaces an empty cell with nothing (otherwise we would have written "nan")
)                                       # result: start-end unit, for example "700-800 M" (M = MHz)

# We build "one sentence of bands per pylon"
bande_par_support = (
    b[["SUP_ID", "BANDE"]]              # [[...]] : we keep only the pylon and its band
    .drop_duplicates()                  # drop_duplicates() : removes duplicates (the same band written several times for one pylon)
    .groupby("SUP_ID")                  # groupby() : sorts the rows into packs, one pack per pylon
    .agg(BANDES=("BANDE", joindre))     # agg() : for each pack, "joindre" sticks the bands together with commas, e.g. "700-800 M, 1800-1880 M"
    .reset_index()                      # reset_index() : puts SUP_ID back as a real column, to do another merge
)


# 6. MERGE EVERYTHING INTO A SINGLE TABLE
# Each .merge() adds columns by linking two tables through a common identifier
df = (support
      # operator (ADM_ID) and commissioning date, through the installation (STA_NM_ANFR)
      .merge(station[["STA_NM_ANFR", "ADM_ID", "DTE_EN_SERVICE"]], on="STA_NM_ANFR", how="left")
      .merge(exploitant, on="ADM_ID", how="left")            # replaces ADM_ID with the name of the operator
      .merge(nature, on="NAT_ID", how="left")                # replaces NAT_ID with the type of support
      .merge(proprio, on="TPO_ID", how="left")               # replaces TPO_ID with the name of the owner
      .merge(ant_par_support, on="SUP_ID", how="left")       # adds the number and types of antennas
      .merge(emet_par_support, on="SUP_ID", how="left")      # adds the technologies
      .merge(bande_par_support, on="SUP_ID", how="left"))    # adds the frequency bands

# Keeps only the supports that have a latitude AND a longitude (.copy() = independent copy)
points = df.dropna(subset=["LAT", "LON"]).copy()
if NB_POINTS:                                                # if we asked for a limited number of points
    points = points.sample(min(NB_POINTS, len(points)))      # we pick NB_POINTS of them at random

print(len(points), "points sur la carte")                    # prints the number of points in the console


# 7. OPERATOR GROUPS AND COLOURS
# Goal: sort the many operators into 5 groups, to give them a colour on the map

def groupe_exploitant(nom):      # we create a function that receives the name of an operator (e.g. "ORANGE service fixe")
    nom = str(nom).upper()       # str() : turns it into text (in case the cell is empty)
                                 # upper() : puts everything in CAPITAL LETTERS, so "Orange", "orange" and "ORANGE" are recognised the same way
    if "ORANGE" in nom:          # "in" : checks whether the word ORANGE is written somewhere in the name
        return "Orange"          # return : the function stops here and gives the answer "Orange"
    if "SFR" in nom:             # otherwise, we test the next word
        return "SFR"
    if "BOUYGUES" in nom:
        return "Bouygues"
    if "FREE" in nom:
        return "Free"
    return "Autres"              # if none of the words was found, it is an "Autres" (other) operator


# One colour for each group (dictionary: group -> colour)
COULEURS = {"Orange": "orange", "SFR": "red", "Bouygues": "blue", "Free": "purple", "Autres": "gray"}

# Creates a GROUPE column by applying the function to each operator name
points["GROUPE"] = points["ADM_LB_NOM"].map(groupe_exploitant)

# Short text displayed in the bubble on click (a long text would slow the map down a lot)
# fillna("?") replaces an empty value with a question mark
def generations(texte):
    texte = str(texte).upper()
    resultat = []
    if "GSM" in texte:
        resultat.append("2G")
    if "UMTS" in texte:
        resultat.append("3G")
    if "LTE" in texte:
        resultat.append("4G")
    if "5G" in texte:
        resultat.append("5G")
    if resultat == []:
        return "Autre"
    return ", ".join(resultat)

points["GENERATIONS"] = points["TECHNOLOGIES"].fillna("").map(generations)

points["TEXTE"] = ("<b>" + points["ADM_LB_NOM"].fillna("?").astype(str) + "</b>"   # operator in bold
                   + "<br>" + points["NAT_LB_NOM"].fillna("?").astype(str)          # <br> = line break, then the nature
                   + "<br>" + points["GENERATIONS"].fillna("?").astype(str)         # then the technologies
                   + "<br>Antennes : " + points["NB_ANTENNES"].fillna(0).astype(int).astype(str)   # then the number of antennas on the support
                   + "<br>Hauteur (m) : " + points["SUP_NM_HAUT"].fillna("?").astype(str)         # then the height of the support in metres
                   + "<br>Propriétaire : " + points["TPO_LB"].fillna("?").astype(str)   # then the owner of the support
                   + "<br>Mise en service : " + points["DTE_EN_SERVICE"].fillna("?").astype(str))   # then the commissioning date


# 8. CREATING THE MAP

carte = folium.Map(
    location=[46.6, 2.5],        # centre of the map (latitude, longitude): the middle of France
    zoom_start=6,                # starting zoom level (6 = the whole of France)
    prefer_canvas=True,          # faster drawing when there are many points
    # Esri background map (free, no key needed)
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    attr="Esri"                  # required credit for the source of the background map
)

# Small piece of JavaScript that says how to draw EACH point (row = [latitude, longitude, colour, text])
# The texts between /* and */ are the JavaScript comments (like # in Python)
callback = """function (row) {                 /* we create a function that receives "row": the information of ONE single point */
    var m = L.circleMarker(                     /* "var m" creates an object called m ; circleMarker = a small circle on the map */
        new L.LatLng(row[0], row[1]),           /* position of the circle: row[0] = latitude, row[1] = longitude */
        {radius: 4,                             /* size of the circle: radius of 4 pixels */
         color: row[2],                         /* colour of the outline: row[2] = colour of the operator */
         fillColor: row[2],                     /* colour of the inside: the same one */
         fillOpacity: 0.7,                      /* transparency of the inside (0 = invisible, 1 = solid) */
         weight: 1});                           /* thickness of the outline: 1 pixel */
    m.on('click', function () {                 /* when we click on this circle, we do what follows */
        this.bindPopup(row[3]).openPopup();     /* "this" = the circle that was clicked ; we create its bubble with row[3] (the text) then open it */
    });                                         /* end of the "on click" part */
    return m;                                   /* the function returns the finished circle, so it can be placed on the map */
};"""
# In plain words: a small circle in the operator's colour, and the bubble is only created when we click on it

# Cluster settings (the bubbles that group nearby points together)
options = {
    "maxClusterRadius": 150,     # bigger = fewer bubbles on the screen = smoother
    "chunkedLoading": True,      # loads the points little by little, without freezing the page
}

# Loop: once for each operator group (Orange, SFR, Bouygues, Free, Autres)
for nom, couleur_groupe in COULEURS.items():
    sous = points[points["GROUPE"] == nom]                   # keeps only the points of this group
    # Creates a layer (can be switched on/off in the menu), with the name and the number of points
    calque = folium.FeatureGroup(name=nom + " (" + str(len(sous)) + ")", show=False).add_to(carte)  # show=False : box unticked at launch
    # List of lists: [latitude, longitude, colour, text] for each point of the group
    donnees = [[r.LAT, r.LON, couleur_groupe, r.TEXTE] for r in sous.itertuples()]
    # Sends all the points at once (without creating 200,000 Python objects), grouped into bubbles
    FastMarkerCluster(donnees, callback=callback, options=options).add_to(calque)

# Adds the menu at the top right to tick/untick each layer
folium.LayerControl().add_to(carte)

# ---------- Save and open ----------
carte.save("carte.html")         # saves the map in an HTML file (in the script's folder)
webbrowser.open("carte.html")    # opens this file in your browser



## DATABASE MANAGEMENT 

"""

chdir("C:\\Users\\alexavi1\\Desktop\\ref")
exploitant = pd.read_csv("sup_exploitant.txt", sep = ";")
nature = pd.read_csv("sup_nature.txt", sep = ";")
proprio = pd.read_csv("sup_proprietaire.txt", sep = ";")
type_antenne = pd.read_csv("sup_type_antenne.txt", sep = ";")
print(exploitant, "\n", nature, "\n", proprio, "\n", type_antenne)

chdir("..\\data")
print(listdir("."))

antenne = pd.read_csv("sup_antenne.txt", sep = ";")
bande = pd.read_csv("sup_bande.txt", sep = ";")
emetteur = pd.read_csv("sup_emetteur.txt", sep = ";")
station = pd.read_csv("sup_station.txt", sep = ";")
support = pd.read_csv("sup_support.txt", sep = ";")
print(antenne, "\n", bande, "\n", emetteur, "\n", station, "\n", support)


"""