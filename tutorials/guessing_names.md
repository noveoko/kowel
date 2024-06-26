# String Prediction based on Length in Pixels

## Problem Definition

![try to read this](cantread.png)

Given a scan of a map and a list of all the street names that may or may not exist in this specific map determine which of the street names a given section of the map most likely contains

## Technology

scikit learn

## Data Collection

For your map, using your softwares measuring tool:
1. Identify a word that is legible and exists in your list of street names
2. Measure the length (in pixels) of the word
3. Measure the length in chars of the word
4. Repeat steps 1-3 until you've collected at least 10-30 examples

## Code

```python
from sklearn.ensemble import RandomForestRegressor

chars = [9,9,5,8,8,10,10,7,12,8]
length = [129.9, 176.1, 89.4,142,132,136,185.2,113.8,224,130]

# Load data
data = pd.DataFrame({'characters_in_word':chars, 'len_in_pixels': length})

# Switch features and target
X = data[['len_in_pixels']]
y = data['characters_in_word']

# Create and fit the model
model = RandomForestRegressor()
model.fit(X, y)

# Make predictions
predictions = model.predict(X)

# Print the results
print("Random Forest Regressor Model")
print("Predictions: ", predictions)

# Predicting for a new pixel width
target = 119 #pixels

new_word = [[target]]
predicted_len = model.predict(new_word)
print(f"Predicted chars in word for pixel width of: {target} for new word with 5 characters: ", predicted_len)
```

## Real-World Case

Length of word to predict: **119 pixels**

Predicted size: **7.63**

Next, I filtered my list of words by len, and then manually checked that they are indeed street names and came up with this list of candidate names:

```python
['Hołówki',
 'Kresowa',
 'Miodowa',
 'Niecala',
 'Narozna',
 'Parkowa',
 'Poleska',
 'Rzeczna',
 'Soborny',
 'Soborna',
 'Szeroka',
 'Szkolna',
 'Wiejska',
 'Wygonna',
 'Wspolna',
 'Zielona',
 'Zórawia']
```

The challenge now is to figure out which of these is most likely. 

## Code Improvement

```python
import math

def predict_word_size(pixel_width=119):
    new_word = [[pixel_width]]
    predicted_len = model.predict(new_word)
    return predicted_len
    
def get_my_name(lengths):
    box = []
    for a in street_names:
        if any([len(a) in lengths]):
            box.append(a)
    return box

def predict_word(pixel_width=119, word_list=street_names, chars_included=None):
    predicted_size = predict_word_size(pixel_width=pixel_width)
    min_size, max_size = [x(predicted_size) for x in [math.floor, math.ceil]]
    print(min_size, max_size)
    by_size = list(filter(lambda x: min_size <= len(x) <= max_size, word_list))
    if chars_included is None:
        return by_size
    return list(filter(lambda x: all([char in x for char in chars_included]), by_size))
    
predictions = predict_word(pixel_width=119, chars_included=[])
print(predictions)
```

# Conclusion

Hopefully this will help you in those difficult cases where you simply cannot determine anything about a string in an image but it's length in pixels. 
