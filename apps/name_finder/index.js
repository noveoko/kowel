// Load the CSV data using d3
d3.csv('WW2_Refugees_Registered_in_Geneva.csv', function(data) {

  // Define the search options for the Fuse.js fuzzy search library
  var options = {
    includeScore: true,
    threshold: 0.3,
    keys: ['Surname']
  }

  // Create a new instance of the Fuse.js fuzzy search class
  var fuse = new Fuse(data, options)

  // Define the function that performs the surname search
  function searchSurnames() {
    var searchInput = document.getElementById('searchInput')
    var resultsList = document.getElementById('resultsList')
    var query = searchInput.value.trim()

    // Clear any existing results from the list
    resultsList.innerHTML = ''

    // Perform the search
    var results = fuse.search(query)

    // Add the matching names to the list
    results.forEach(function(result) {
      var name = result.item['Full Name']
      var score = result.score.toFixed(2)
      var listItem = document.createElement('li')
      listItem.textContent = name + ' (' + score + ')'
      resultsList.appendChild(listItem)
    })
  }
})
