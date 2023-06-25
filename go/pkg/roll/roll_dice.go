package roll

import (
        "math/rand"
        "strconv"
        "time"
)

func Roll() string {
        fmt.Println("rolling the dice")
        return generateNumber()
}

func generateNumber() string {
        source := rand.NewSource(time.Now().UnixNano())
        random := rand.New(source)
        return strconv.Itoa(random.Intn(100))
}
