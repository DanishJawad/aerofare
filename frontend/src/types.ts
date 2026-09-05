export interface Airport {
  id: number
  name: string
  city: string
  country: string
}

export interface Flight {
  id: number
  airline_name: string
  departure_airport: number
  arrival_airport: number
  start_time: string     
  end_time: string
  price: string              
  total_seats: number
  available_seats: number
  flight_class: "economy" | "business" | "first"
}